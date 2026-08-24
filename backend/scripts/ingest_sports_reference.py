"""
Ingest 2025-26 college basketball rosters and per-game stats from Sports Reference.
Season pages use end-year URL: /schools/{slug}/2026.html
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup, Comment

import sys

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(BACKEND_ROOT))

from generate_demo_data import SEASON_LABEL, SEASON_YEAR, _team_profile
from models.class_year import normalize_class_year
from teams_universe import TEAMS_SPEC
from team_slugs import TEAM_SLUGS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "sr_cache"
SR_YEAR = 2026  # end-year URL on Sports Reference (2026 = 2025-26 season)
STATS_LABEL = "2025-26"
USER_AGENT = "DevelopmentIQ-Academic/1.0 (college basketball analytics internship)"
REQUEST_DELAY = 8.0
MIN_MPG = 10
MIN_MINUTES = 250
MAX_RETRIES = 6


def configure_ingest(
    *,
    sr_year: int = 2026,
    cache_dir: Path | None = None,
    stats_label: str | None = None,
) -> None:
    """Switch target season and cache directory (e.g. prior year for YoY calibration)."""
    global SR_YEAR, CACHE_DIR, STATS_LABEL
    SR_YEAR = sr_year
    CACHE_DIR = cache_dir or DATA_DIR / "sr_cache"
    STATS_LABEL = stats_label or (
        "2024-25" if sr_year == 2025 else "2025-26" if sr_year == 2026 else str(sr_year - 1)
    )


def fetch_html(slug: str) -> str:
    url = f"https://www.sports-reference.com/cbb/schools/{slug}/{SR_YEAR}.html"
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            soup = BeautifulSoup(raw, "html.parser")
            for node in soup.find_all(string=lambda t: isinstance(t, Comment)):
                if "table" in str(node).lower():
                    node.replace_with(BeautifulSoup(str(node), "html.parser"))
            return str(soup)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"    rate limited — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            last_err = e
            time.sleep(10 * (attempt + 1))
    raise last_err or RuntimeError(f"Failed to fetch {slug}")


def _parse_pct(val) -> float:
    if pd.isna(val):
        return 0.0
    s = str(val).strip()
    if s.endswith("%"):
        return float(s.replace("%", "")) / 100
    try:
        v = float(s)
        return v / 100 if v > 1 else v
    except ValueError:
        return 0.0


def _num(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def resolve_mpg_and_minutes(mp_raw: float, games: int) -> tuple[float, float]:
    """
    Sports Reference per-game tables use MP as MPG (often with decimals).
    Totals tables use MP as season minutes (integer, typically MP/G < 6).
    """
    g = max(int(games), 1)
    mp = float(mp_raw)
    if mp <= 0:
        return 0.0, 0.0
    has_decimal = abs(mp - round(mp)) >= 0.05
    per_game_rate = mp / g
    if not has_decimal and mp > g and per_game_rate <= 6.0:
        return round(per_game_rate, 1), round(mp, 1)
    if mp > 55:
        return round(per_game_rate, 1), round(mp, 1)
    mpg = round(mp, 1)
    return mpg, round(mpg * g, 1)


def resolve_points_and_ppg(
    row: pd.Series | dict, games: int, mpg: float, minutes: float
) -> tuple[float, float]:
    """SR per-game tables store PTS as PPG; totals tables store season points."""
    g = max(int(games), 1)

    def _get(key: str) -> float:
        if isinstance(row, dict):
            return _num(row.get(key, 0))
        return _num(row.get(key, 0))

    mp_raw = _get("MP")
    pts = _get("PTS")
    fg = _get("FG")
    tp = _get("3P")
    ft = _get("FT")
    fga = _get("FGA")

    if pts <= 0 and (fg > 0 or fga > 0):
        pts = fg * 2 + tp + ft

    has_decimal = abs(mp_raw - round(mp_raw)) >= 0.05
    rate = mp_raw / g if g else mp_raw

    if not has_decimal and mp_raw > g and rate <= 6.0 and pts > 0:
        return round(pts / g, 1), round(pts, 1)
    if pts > 0 and mpg > 0 and pts > mpg * g * 0.5 and (pts / g) <= 50:
        return round(pts / g, 1), round(pts, 1)

    ppg = round(pts, 1)
    return ppg, round(ppg * g, 1)


def normalize_player_record(player: dict) -> dict:
    """Repair rows where season total minutes or points were mis-parsed."""
    out = dict(player)
    g = max(int(out.get("games_played", 1)), 1)
    mpg, minutes = resolve_mpg_and_minutes(float(out.get("mpg", 0)), g)
    out["mpg"] = mpg
    out["minutes"] = minutes

    ppg, points = resolve_points_and_ppg(
        {
            "MP": out.get("mpg", 0),
            "PTS": out.get("ppg", 0) if out.get("ppg", 0) > 0 else out.get("points", 0) / g,
            "FG": 0,
            "FGA": out.get("three_point_attempts", 0) / max(g, 1),
        },
        g,
        mpg,
        minutes,
    )
    if float(out.get("ppg", 0) or 0) <= 0 and ppg > 0:
        out["ppg"] = ppg
        out["points"] = points
    return out


def prepare_html_soup(html: str) -> BeautifulSoup:
    """Unwrap HTML comments so tables inside comments are discoverable."""
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(string=lambda t: isinstance(t, Comment)):
        if "table" in str(node).lower():
            node.replace_with(BeautifulSoup(str(node), "html.parser"))
    return soup


def _advanced_stats_from_row(row: pd.Series) -> dict:
    def fcol(*names: str, ndigits: int = 1) -> float | None:
        for n in names:
            if n not in row.index:
                continue
            v = row[n]
            if pd.isna(v):
                continue
            try:
                return round(float(v), ndigits)
            except (TypeError, ValueError):
                continue
        return None

    stats: dict = {}
    bpm = fcol("BPM")
    if bpm is not None:
        stats["bpm"] = bpm
        obpm = fcol("OBPM")
        dbpm = fcol("DBPM")
        if obpm is not None:
            stats["obpm"] = obpm
        if dbpm is not None:
            stats["dbpm"] = dbpm
    per = fcol("PER")
    if per is not None:
        stats["per"] = per
    ws = fcol("WS", ndigits=2)
    if ws is not None:
        stats["win_shares"] = ws
    ws40 = fcol("WS/40", ndigits=3)
    if ws40 is not None:
        stats["win_shares_per_40"] = ws40
    return stats


def parse_players_advanced(html: str) -> dict[str, dict]:
    """Player name → BPM/PER/WS fields from SR players_advanced table."""
    soup = prepare_html_soup(html)
    table = soup.find("table", id="players_advanced")
    if not table:
        return {}
    df = pd.read_html(StringIO(str(table)))[0]
    if "Player" not in df.columns:
        return {}
    df = df[df["Player"].notna()].copy()
    df = df[~df["Player"].astype(str).str.contains("Team Totals", na=False)]
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        name = str(row["Player"]).strip()
        stats = _advanced_stats_from_row(row)
        if stats:
            out[name] = stats
    return out


def merge_advanced_stats(
    players: list[dict], advanced_by_name: dict[str, dict]
) -> tuple[list[dict], int]:
    if not advanced_by_name:
        return players, 0
    by_lower = {k.lower(): v for k, v in advanced_by_name.items()}
    matched = 0
    out: list[dict] = []
    for p in players:
        rec = dict(p)
        name = str(rec.get("player_name", "")).strip()
        adv = advanced_by_name.get(name) or by_lower.get(name.lower())
        if adv:
            rec.update(adv)
            matched += 1
        out.append(rec)
    return out, matched


def parse_player_table(html: str) -> pd.DataFrame:
    tables = pd.read_html(StringIO(html))
    best: pd.DataFrame | None = None
    for df in tables:
        cols = [str(c).lower() for c in df.columns]
        if "player" in cols and "mp" in cols and "pts" in cols:
            if "rk" in cols or str(df.columns[0]).lower() == "rk":
                cleaned = df[df["Player"].notna() & (df["Player"] != "Player")].copy()
                cleaned = cleaned[
                    ~cleaned["Player"].astype(str).str.contains("Team Totals", na=False)
                ]
                if best is None or len(cleaned) > len(best):
                    best = cleaned
    if best is not None and len(best) > 0:
        return best
    raise ValueError("Per-game player table not found")


def parse_team_efficiency_from_html(html: str) -> dict:
    """
    Team ORtg, DRtg, and pace from Sports Reference season-total_totals (Team vs Opponent).
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="season-total_totals")
    if not table:
        return {}

    team_cells: dict = {}
    opp_cells: dict = {}
    for row in table.find_all("tr"):
        th = row.find("th")
        label = th.get_text(strip=True) if th else ""
        cells = {
            c.get("data-stat"): c.get_text(strip=True)
            for c in row.find_all(["td", "th"])
            if c.get("data-stat")
        }
        if label == "Team":
            team_cells = cells
        elif label == "Opponent":
            opp_cells = cells

    required_team = ("pts", "fga", "fta", "tov", "orb", "mp")
    required_opp = ("opp_pts", "opp_fga", "opp_fta", "opp_tov", "opp_orb")
    if not all(k in team_cells for k in required_team) or not all(k in opp_cells for k in required_opp):
        return {}

    def possessions(c: dict, prefix: str = "") -> float:
        p = prefix
        fga = _num(c.get(f"{p}fga", 0))
        fta = _num(c.get(f"{p}fta", 0))
        tov = _num(c.get(f"{p}tov", 0))
        orb = _num(c.get(f"{p}orb", 0))
        return fga + 0.44 * fta - orb + tov

    team_poss = possessions(team_cells)
    opp_poss = possessions(
        {
            "fga": opp_cells.get("opp_fga"),
            "fta": opp_cells.get("opp_fta"),
            "tov": opp_cells.get("opp_tov"),
            "orb": opp_cells.get("opp_orb"),
        }
    )
    if team_poss <= 0 or opp_poss <= 0:
        return {}

    mp = _num(team_cells.get("mp", 0))
    pts = _num(team_cells.get("pts", 0))
    opp_pts = _num(opp_cells.get("opp_pts", 0))
    pace = 40 * (team_poss + opp_poss) / 2 / (mp / 5) if mp > 0 else 0.0

    return {
        "offensive_rating": round(100 * pts / team_poss, 1),
        "defensive_rating": round(100 * opp_pts / opp_poss, 1),
        "pace": round(pace, 1),
    }


def estimate_team_efficiency(team: dict) -> dict:
    """
    Fallback when SR season-total_totals is unavailable (e.g. rate-limited re-fetch).
    Estimates vary by team so pool ranks are meaningful; re-run ingest to replace with SR values.
    """
    efg = float(team.get("efg_pct", 0.48))
    tov = float(team.get("turnover_rate", 0.17))
    orb = float(team.get("offensive_rebound_rate", 0.14))
    ftr = float(team.get("free_throw_rate", 0.33))
    drb = float(team.get("defensive_rebound_rate", 0.37))
    ast = float(team.get("assist_rate", 0.55))
    stl = float(team.get("steal_rate", 0.004))
    blk = float(team.get("block_rate", 0.003))
    foul = float(team.get("foul_rate", 0.012))

    ortg = 68 + 93 * efg - 33 * tov + 24 * orb + 17 * ftr
    # Opponent scoring proxy from team defensive box-rate inputs (not true DRtg).
    drtg = 108 + 42 * tov - 36 * drb - 95 * stl - 70 * blk + 22 * foul
    pace = 58 + 22 * tov + 12 * ast
    return {
        "offensive_rating": round(ortg, 1),
        "defensive_rating": round(drtg, 1),
        "pace": round(pace, 1),
    }


def parse_team_row(html: str) -> dict:
    tables = pd.read_html(StringIO(html))
    for df in tables:
        cols = [str(c) for c in df.columns]
        if "MP" in cols and "FG%" in cols and "TOV" in cols:
            team_rows = df[df.iloc[:, 0].astype(str).str.contains("Team", na=False)]
            if len(team_rows):
                r = team_rows.iloc[0]
                g = _num(r.get("G", 30), 30)
                fga = _num(r.get("FGA", 60))
                fta = _num(r.get("FTA", 20))
                tov = _num(r.get("TOV", 12))
                orb = _num(r.get("ORB", 10))
                pts = _num(r.get("PTS", 75))
                poss_pg = max(fga + 0.44 * fta - orb + tov, 0.1)
                mp_pg = max(_num(r.get("MP", 40)), 1)
                return {
                    "games_played": int(g),
                    "offensive_rating": round(100 * pts / poss_pg, 1),
                    "defensive_rating": 100.0,
                    "pace": round(40 * poss_pg / mp_pg, 1),
                    "efg_pct": _parse_pct(r.get("FG%", 0.48)),
                    "three_point_pct": _parse_pct(r.get("3P%", 0.34)),
                    "three_point_rate": _num(r.get("3PA", 20)) / max(_num(r.get("FGA", 60)), 1),
                    "turnover_rate": _num(r.get("TOV", 12)) / max(_num(r.get("FGA", 60)), 1),
                    "offensive_rebound_rate": _num(r.get("ORB", 10)) / max(_num(r.get("TRB", 35)), 1) * 0.45,
                    "defensive_rebound_rate": _num(r.get("DRB", 20)) / max(_num(r.get("TRB", 35)), 1) * 0.55,
                    "free_throw_rate": _num(r.get("FTA", 15)) / max(_num(r.get("FGA", 60)), 1),
                    "free_throw_pct": _parse_pct(r.get("FT%", 0.70)),
                    "two_point_pct": (
                        max(_num(r.get("FG", 28)) - _num(r.get("3P", 8)), 0)
                        / max(_num(r.get("FGA", 60)) - _num(r.get("3PA", 20)), 1)
                    ),
                    "assist_rate": _num(r.get("AST", 14)) / max(_num(r.get("FG", 28)), 1),
                    "block_rate": _num(r.get("BLK", 3)) / max(g, 1) / 40,
                    "steal_rate": _num(r.get("STL", 6)) / max(g, 1) / 40,
                    "foul_rate": _num(r.get("PF", 16)) / max(g, 1) / 40,
                }
    return {}


def class_from_roster(html: str) -> dict[str, str]:
    """Player name -> class year from roster table (Sports Reference FR/SO/JR/SR)."""
    mapping: dict[str, str] = {}
    tables = pd.read_html(StringIO(html))
    for df in tables:
        cols = [str(c) for c in df.columns]
        if "Player" not in cols or "Class" not in cols:
            continue
        for _, row in df.iterrows():
            name = str(row.get("Player", "")).strip()
            if not name or name == "Player" or name.lower() == "nan":
                continue
            cls = normalize_class_year(row.get("Class"))
            if cls != "Unknown":
                mapping[name] = cls
                # Also index a Jr./Sr. suffix-stripped key for stats-table name mismatches.
                alt = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", name, flags=re.I).strip()
                if alt and alt != name:
                    mapping.setdefault(alt, cls)
    return mapping


def _lookup_class(class_map: dict[str, str], name: str) -> str | None:
    if name in class_map:
        return class_map[name]
    alt = re.sub(r"\s+(jr|sr|ii|iii|iv)\.?$", "", name, flags=re.I).strip()
    if alt in class_map:
        return class_map[alt]
    # Case-insensitive fallback
    low = {k.lower(): v for k, v in class_map.items()}
    if name.lower() in low:
        return low[name.lower()]
    if alt.lower() in low:
        return low[alt.lower()]
    return None


def player_rows_from_df(
    df: pd.DataFrame, team_id: str, class_map: dict[str, str], games: int
) -> list[dict]:
    rows = []
    for i, row in df.iterrows():
        name = str(row["Player"]).strip()
        g = int(_num(row.get("G", games)))
        mpg, minutes = resolve_mpg_and_minutes(_num(row.get("MP", 0)), g)
        if mpg < MIN_MPG and minutes < MIN_MINUTES:
            continue

        fga = _num(row.get("FGA", 0))
        fta = _num(row.get("FTA", 0))
        tov = _num(row.get("TOV", 0))
        poss = max(fga + 0.44 * fta + tov, 0.1)
        ppg, points = resolve_points_and_ppg(row, g, mpg, minutes)
        if ppg <= 0 and minutes < MIN_MINUTES:
            continue
        efg = _parse_pct(row.get("eFG%", row.get("FG%", 0.45)))

        tp_att_pg = _num(row.get("3PA", 0))
        tp_att_season = int(round(tp_att_pg * g))
        ft_att_season = int(round(fta * g))
        fg_made_pg = _num(row.get("FG", 0))
        fga_pg = max(fga, 0.1)
        two_pm_pg = max(fg_made_pg - tp_att_pg, 0)
        two_pa_pg = max(fga_pg - tp_att_pg, 0.1)
        two_point_pct = round(two_pm_pg / two_pa_pg, 3)
        three_point_attempt_rate = round(tp_att_pg / fga_pg, 3)
        free_throw_rate_player = round(fta / fga_pg, 3)
        ast_pg = round(_num(row.get("AST", 0)) / g, 2)
        tov_pg = round(tov / g, 2)
        ast_to = round(ast_pg / max(tov_pg, 0.1), 2)
        orb_pg = round(_num(row.get("ORB", 0)) / g, 2)
        drb_pg = round(_num(row.get("DRB", 0)) / g, 2)
        stl_pg = round(_num(row.get("STL", 0)) / g, 2)
        blk_pg = round(_num(row.get("BLK", 0)) / g, 2)
        pf_pg = round(_num(row.get("PF", 0)) / g, 2)
        fouls_per_40 = round(pf_pg * 40 / max(mpg, 1), 2)
        poss_pg = max(fga_pg + 0.44 * fta + tov_pg, 0.1)
        steal_pct = round(100 * stl_pg / poss_pg, 2)
        block_pct = round(100 * blk_pg / poss_pg, 2)
        fga_season = int(round(fga_pg * g))

        class_year = _lookup_class(class_map, name)
        rows.append({
            "player_id": f"{team_id}_{re.sub(r'[^a-z0-9]+', '_', name.lower())}",
            "player_name": name,
            "team_id": team_id,
            "position": str(row.get("Pos", "G"))[:1] or "G",
            "class_year": class_year or "Unknown",
            "class_year_source": "sports_reference_roster" if class_year else "unknown",
            "games_played": g,
            "minutes": minutes,
            "mpg": round(mpg, 1),
            "usage_rate": round(min(0.35, poss / 28), 3),
            "points": points,
            "ppg": ppg,
            "efg_pct": round(efg, 3),
            "ts_pct": round(min(0.72, efg + 0.02), 3),
            "field_goal_attempts": fga_season,
            "three_point_attempts": tp_att_season,
            "three_point_pct": _parse_pct(row.get("3P%", 0.33)),
            "three_point_attempt_rate": three_point_attempt_rate,
            "free_throw_attempts": ft_att_season,
            "free_throw_pct": _parse_pct(row.get("FT%", 0.72)),
            "free_throw_rate": free_throw_rate_player,
            "two_point_pct": two_point_pct,
            "assist_turnover_ratio": ast_to,
            "turnover_rate": round(min(0.28, tov / poss), 3),
            "assist_rate": round(min(0.35, _num(row.get("AST", 0)) / poss), 3),
            "offensive_rebound_rate": round(min(0.18, _num(row.get("ORB", 0)) / max(mpg, 1) * 0.04), 3),
            "defensive_rebound_rate": round(min(0.28, _num(row.get("DRB", 0)) / max(mpg, 1) * 0.055), 3),
            "steal_rate": round(min(0.06, _num(row.get("STL", 0)) / max(mpg, 1) * 0.012), 3),
            "block_rate": round(min(0.12, _num(row.get("BLK", 0)) / max(mpg, 1) * 0.018), 3),
            "foul_rate": round(min(0.09, _num(row.get("PF", 0)) / max(mpg, 1) * 0.014), 3),
            "orb_per_game": orb_pg,
            "drb_per_game": drb_pg,
            "ast_per_game": ast_pg,
            "tov_per_game": tov_pg,
            "stl_per_game": stl_pg,
            "blk_per_game": blk_pg,
            "pf_per_game": pf_pg,
            "fouls_per_40": fouls_per_40,
            "steal_pct": steal_pct,
            "block_pct": block_pct,
            "player_ortg": None,
            "player_drtg": None,
            "data_source": f"Sports Reference {STATS_LABEL}",
        })
    return rows


def _cache_path(team_id: str) -> Path:
    return CACHE_DIR / f"{team_id}.json"


def _load_cache(team_id: str) -> dict | None:
    p = _cache_path(team_id)
    if p.exists():
        return json.loads(p.read_text())
    return None


def _save_cache(team_id: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(team_id).write_text(json.dumps(payload, indent=2))


def ingest_team(
    tid: str, tname: str, conf: str, slug: str, *, force_refresh: bool = False
) -> tuple[dict, list[dict]]:
    cached = _load_cache(tid)
    if cached and not force_refresh:
        return cached["team"], cached["players"]

    html = fetch_html(slug)
    prof = parse_team_row(html) or {"games_played": 32}
    prof.update(parse_team_efficiency_from_html(html))
    if prof.get("defensive_rating") in (None, 100.0):
        prof.update(estimate_team_efficiency(prof))
    team_row = {
        "team_id": tid,
        "team_name": tname,
        "conference": conf,
        "season": SR_YEAR,
        "data_source": f"Sports Reference {STATS_LABEL}",
        **prof,
    }
    pdf = parse_player_table(html)
    cmap = class_from_roster(html)
    players = player_rows_from_df(pdf, tid, cmap, int(prof.get("games_played", 32)))
    advanced = parse_players_advanced(html)
    players, _ = merge_advanced_stats(players, advanced)
    _save_cache(tid, {"team": team_row, "players": players})
    time.sleep(REQUEST_DELAY)
    return team_row, players


def ingest_all(only_missing: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    team_rows = []
    player_rows = []
    failed = []

    for tid, tname, conf in TEAMS_SPEC:
        slug = TEAM_SLUGS.get(tid)
        if not slug:
            failed.append(tid)
            continue
        if only_missing and _load_cache(tid):
            cached = _load_cache(tid)
            team_rows.append(cached["team"])
            player_rows.extend(cached["players"])
            continue
        try:
            team_row, new_players = ingest_team(tid, tname, conf, slug)
            team_rows.append(team_row)
            player_rows.extend(new_players)
            print(f"  ✓ {tname}: {len(new_players)} rotation players")
        except Exception as e:
            print(f"  ✗ {tname}: {e}")
            failed.append(tid)
            time.sleep(REQUEST_DELAY * 2)

    # Use cache for any failures on final merge
    for tid, tname, conf in TEAMS_SPEC:
        if tid in [t["team_id"] for t in team_rows]:
            continue
        cached = _load_cache(tid)
        if cached:
            team_rows.append(cached["team"])
            player_rows.extend(cached["players"])

    if failed:
        print(f"Warning: failed teams ({len(failed)}): {failed}")

    teams = pd.DataFrame(team_rows)
    players = pd.DataFrame(player_rows)
    if not players.empty:
        players = players.drop_duplicates(subset=["player_id"])
        players = players[(players["mpg"] >= MIN_MPG) | (players["minutes"] >= MIN_MINUTES)]
    return teams, players


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--missing-only", action="store_true", help="Only fetch teams not in cache")
    parser.add_argument(
        "--enrich-advanced-only",
        action="store_true",
        help="Re-fetch SR pages to merge players_advanced (BPM/PER/WS) into existing caches",
    )
    parser.add_argument("--delay", type=float, default=6.0, help="Seconds between requests")
    parser.add_argument(
        "--sr-year",
        type=int,
        default=2026,
        help="Sports Reference end-year in URL (2025=2024-25, 2026=2025-26)",
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="",
        help="Cache folder under backend/data (default: sr_cache or sr_cache_prior for 2025)",
    )
    args = parser.parse_args()
    REQUEST_DELAY = args.delay
    cache = DATA_DIR / (args.cache_dir or ("sr_cache_prior" if args.sr_year == 2025 else "sr_cache"))
    configure_ingest(sr_year=args.sr_year, cache_dir=cache)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if args.enrich_advanced_only:
        from enrich_sr_cache_advanced import enrich_all_caches

        print(f"Enriching BPM/PER/WS on cached rosters (delay={REQUEST_DELAY}s)...")
        enrich_all_caches(delay=REQUEST_DELAY)
        raise SystemExit(0)
    print(f"Ingesting {STATS_LABEL} from Sports Reference (delay={REQUEST_DELAY}s)...")
    teams, players = ingest_all(only_missing=args.missing_only)
    teams.to_csv(DATA_DIR / "teams_demo.csv", index=False)
    players.to_csv(DATA_DIR / "players_demo.csv", index=False)
    meta = {
        "label": f"{STATS_LABEL} PUBLIC DATA",
        "description": (
            f"Team and player statistics ingested from Sports Reference ({STATS_LABEL} season)."
        ),
        "season": SR_YEAR,
        "season_label": STATS_LABEL,
        "teams_count": len(teams),
        "players_count": len(players),
        "sources": ["Sports Reference"],
    }
    with open(DATA_DIR / "data_manifest.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved {len(teams)} teams, {len(players)} players → {DATA_DIR}")
