"""
DevelopmentIQ FastAPI backend.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import sys

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DB_PATH = BACKEND_ROOT / "data" / "developmentiq.db"
FEATURED_TEAM_ID = "san_jose_state"

from models.projection_impact import simulate_impacts_from_sliders  # noqa: E402
from models.simulator_presets import (  # noqa: E402
    apply_suggested_value_dampening,
    simulator_preset_payload,
)

app = FastAPI(
    title="DevelopmentIQ API",
    description="College Basketball Player Development Priority Engine",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Database not initialized. Run: python scripts/seed_database.py",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def fetch_top_priority_row(conn: sqlite3.Connection, player_id: str) -> sqlite3.Row | None:
    """Top Priority via rank_player_priorities (same rules as leverage board seeding)."""
    import pandas as pd

    from models.scoring import rank_player_priorities

    rows = conn.execute(
        "SELECT * FROM development_priority_scores WHERE player_id = ?",
        (player_id,),
    ).fetchall()
    if not rows:
        return None
    ranked = rank_player_priorities(pd.DataFrame([dict(r) for r in rows]))
    if ranked.empty:
        return None
    top = ranked.iloc[0]
    for r in rows:
        if r["skill_category"] == top["skill_category"]:
            return r
    return rows[0]


def player_stat_ranks(conn: sqlite3.Connection, player_id: str) -> dict[str, dict[str, int]]:
    stat_cols = {
        "ppg": ("ppg", False),
        "ts_pct": ("ts_pct", False),
        "usage_rate": ("usage_rate", False),
        "three_point_pct": ("three_point_pct", False),
        "three_point_attempt_rate": ("three_point_attempt_rate", False),
        "free_throw_rate": ("free_throw_rate", False),
        "assist_turnover_ratio": ("assist_turnover_ratio", False),
        "two_point_pct": ("two_point_pct", False),
        "fouls_per_40": ("fouls_per_40", True),
        "steal_pct": ("steal_pct", False),
        "block_pct": ("block_pct", False),
        "bpm": ("bpm", False),
        "obpm": ("obpm", False),
        "dbpm": ("dbpm", False),
        "per": ("per", False),
        "player_ortg": ("player_ortg", False),
        "player_drtg": ("player_drtg", True),
        "win_shares": ("win_shares", False),
        "win_shares_per_40": ("win_shares_per_40", False),
        "rim_attempt_rate": ("rim_attempt_rate", False),
        "rim_fg_pct": ("rim_fg_pct", False),
        "midrange_attempt_rate": ("midrange_attempt_rate", False),
        "midrange_fg_pct": ("midrange_fg_pct", False),
        "corner_three_attempt_rate": ("corner_three_attempt_rate", False),
    }
    total_players = conn.execute("SELECT COUNT(*) as count FROM players").fetchone()["count"]
    ranks: dict[str, dict[str, int]] = {}
    for key, (col, lower_is_better) in stat_cols.items():
        stat = conn.execute(
            f"SELECT {col} as value FROM players WHERE player_id = ?",
            (player_id,),
        ).fetchone()
        if not stat or stat["value"] is None:
            continue
        comparator = "<" if lower_is_better else ">"
        players_ahead = conn.execute(
            f"""
            SELECT COUNT(*) as count
            FROM players
            WHERE {col} IS NOT NULL AND {col} {comparator} ?
            """,
            (stat["value"],),
        ).fetchone()["count"]
        ranks[key] = {"rank": players_ahead + 1, "pool": total_players}
    return ranks


@app.get("/")
def root() -> dict[str, str]:
    return {
        "app": "DevelopmentIQ API",
        "docs": "Use /docs for interactive API explorer",
        "health": "/api/health",
        "frontend": "Open http://localhost:5173 for the dashboard (npm run dev in frontend/)",
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "database": str(DB_PATH.exists())}


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    conn = get_conn()
    teams = conn.execute("SELECT COUNT(*) as c FROM teams").fetchone()["c"]
    players = conn.execute("SELECT COUNT(*) as c FROM players").fetchone()["c"]
    conn.close()
    manifest_path = DB_PATH.parent / "data_manifest.json"
    manifest = {}
    if manifest_path.exists():
        import json
        manifest = json.loads(manifest_path.read_text())
    return {
        "teams_count": teams,
        "players_count": players,
        "season": manifest.get("season", 2026),
        "season_label": manifest.get("season_label", "2026-27"),
        "stats_season_label": manifest.get("stats_season_label", "2025-26"),
        "data_label": manifest.get("label", "2026-27 ROSTERS · SR STATS"),
        "description": manifest.get("description", ""),
        "roster_projection_last_updated": manifest.get(
            "roster_projection_last_updated", "2026-05-28"
        ),
        "roster_status_warning": manifest.get("roster_status_warning", ""),
        "roster_status_override_count": manifest.get("roster_status_override_count", 0),
    }


@app.get("/api/teams")
def list_teams() -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM teams ORDER BY team_name"
    ).fetchall()
    conn.close()
    return rows_to_dicts(rows)


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(12, ge=1, le=30),
) -> dict[str, Any]:
    """Search teams and players by name (for workspace tabs)."""
    term = f"%{q.strip().lower()}%"
    conn = get_conn()

    team_rows = conn.execute(
        """
        SELECT team_id, team_name, conference
        FROM teams
        WHERE LOWER(team_name) LIKE ? OR LOWER(conference) LIKE ? OR LOWER(team_id) LIKE ?
        ORDER BY team_name
        LIMIT ?
        """,
        (term, term, term, limit),
    ).fetchall()

    player_rows = conn.execute(
        """
        SELECT p.player_id, p.player_name, p.team_id, p.position, p.mpg,
               t.team_name, t.conference
        FROM players p
        JOIN teams t ON p.team_id = t.team_id
        WHERE LOWER(p.player_name) LIKE ?
        ORDER BY p.mpg DESC
        LIMIT ?
        """,
        (term, limit),
    ).fetchall()
    conn.close()

    teams_out = [
        {
            "type": "team",
            "team_id": r["team_id"],
            "team_name": r["team_name"],
            "conference": r["conference"],
        }
        for r in team_rows
    ]
    players_out = [
        {
            "type": "player",
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "team_id": r["team_id"],
            "team_name": r["team_name"],
            "conference": r["conference"],
            "position": r["position"],
            "mpg": r["mpg"],
        }
        for r in player_rows
    ]
    return {"query": q.strip(), "teams": teams_out, "players": players_out}


@app.get("/api/teams/{team_id}")
def get_team(team_id: str) -> dict:
    conn = get_conn()
    team = conn.execute("SELECT * FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    if not team:
        conn.close()
        raise HTTPException(404, "Team not found")
    needs = conn.execute(
        "SELECT * FROM team_need_scores WHERE team_id = ?", (team_id,)
    ).fetchone()
    conn.close()
    needs_dict = dict(needs) if needs else {}
    raw_exp = needs_dict.pop("need_explanations", None)
    if raw_exp:
        import json

        try:
            needs_dict["need_explanations"] = json.loads(raw_exp)
        except json.JSONDecodeError:
            needs_dict["need_explanations"] = {}
    return {"team": dict(team), "needs": needs_dict}


@app.get("/api/teams/{team_id}/players")
def team_players(team_id: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT p.*, d.development_leverage_score, d.top_priority, d.second_priority,
               d.third_priority
        FROM players p
        LEFT JOIN development_leverage_scores d ON p.player_id = d.player_id
        WHERE p.team_id = ?
        ORDER BY p.mpg DESC
        """,
        (team_id,),
    ).fetchall()
    conn.close()
    return rows_to_dicts(rows)


@app.get("/api/teams/{team_id}/development-board")
def development_board(team_id: str) -> list[dict]:
    conn = get_conn()
    from models.roster_transfers import is_transfer_player, transfer_from_school

    players = conn.execute(
        """
        SELECT player_id, player_name, position, class_year_2026_27, mpg, data_source
        FROM players WHERE team_id = ?
        """,
        (team_id,),
    ).fetchall()
    board = []
    for pl in players:
        pid = pl["player_id"]
        top = fetch_top_priority_row(conn, pid)
        lev = conn.execute(
            "SELECT development_leverage_score FROM development_leverage_scores WHERE player_id = ?",
            (pid,),
        ).fetchone()
        if top:
            ds = pl["data_source"]
            board.append({
                "player_id": pid,
                "player_name": pl["player_name"],
                "position": pl["position"],
                "class_year_2026_27": pl["class_year_2026_27"] or "Unknown",
                "mpg": pl["mpg"],
                "is_transfer_in": is_transfer_player(
                    data_source=ds,
                    player_name=pl["player_name"],
                    team_id=team_id,
                ),
                "transfer_from": transfer_from_school(ds),
                "top_priority": top["skill_category"],
                "development_priority_score": top["development_priority_score"],
                "projected_points_added": top["projected_points_added"],
                "development_leverage_score": lev["development_leverage_score"] if lev else None,
                "main_reason": top["explanation"],
            })
    conn.close()
    board.sort(key=lambda x: x.get("development_priority_score") or 0, reverse=True)
    return board


@app.get("/api/players/{player_id}")
def get_player(player_id: str) -> dict:
    conn = get_conn()
    player = conn.execute("SELECT * FROM players WHERE player_id = ?", (player_id,)).fetchone()
    if not player:
        conn.close()
        raise HTTPException(404, "Player not found")
    team = conn.execute(
        "SELECT * FROM teams WHERE team_id = ?", (player["team_id"],)
    ).fetchone()
    priorities = conn.execute(
        """
        SELECT * FROM development_priority_scores
        WHERE player_id = ?
        ORDER BY actionable DESC, development_priority_score DESC
        """,
        (player_id,),
    ).fetchall()
    opps = conn.execute(
        "SELECT * FROM player_opportunity_scores WHERE player_id = ?", (player_id,)
    ).fetchone()
    leverage = conn.execute(
        "SELECT * FROM development_leverage_scores WHERE player_id = ?", (player_id,)
    ).fetchone()
    stat_ranks = player_stat_ranks(conn, player_id)
    conn.close()
    from models.shot_profile import (
        has_any_shot_profile,
        has_rim_location_data,
        rim_pressure_skill_label,
    )

    player_dict = dict(player)
    priority_rows = rows_to_dicts(priorities)
    dps_by_skill = {row["skill_category"]: row["development_priority_score"] for row in priority_rows}
    opportunity_by_skill = {
        row["skill_category"]: row["player_improvement_opportunity"] for row in priority_rows
    }
    return {
        "player": player_dict,
        "team": dict(team) if team else {},
        "priorities": priority_rows,
        "opportunities": dict(opps) if opps else {},
        "leverage": dict(leverage) if leverage else {},
        "stat_ranks": stat_ranks,
        "rim_pressure_label": rim_pressure_skill_label(player_dict),
        "shot_profile_available": has_any_shot_profile(player_dict),
        "rim_location_tracked": has_rim_location_data(player_dict),
        "simulator_presets": simulator_preset_payload(
            player_dict, dps_by_skill, opportunity_by_skill
        ),
    }


@app.get("/api/leaderboard/leverage")
def leverage_leaderboard(
    limit: int = Query(50, le=1000),
    team_id: str | None = None,
) -> list[dict]:
    conn = get_conn()
    q = """
        SELECT p.player_name, p.player_id, p.position, p.class_year_2026_27, p.mpg, p.team_id,
               t.team_name, t.conference, d.development_leverage_score, d.top_priority,
               d.second_priority, d.third_priority,
               COALESCE(pri.projected_points_added, 0) AS projected_impact,
               COALESCE(pri.team_need_alignment, 0) AS team_need_match
        FROM development_leverage_scores d
        JOIN players p ON d.player_id = p.player_id
        JOIN teams t ON p.team_id = t.team_id
        LEFT JOIN development_priority_scores pri
            ON pri.player_id = d.player_id AND pri.skill_category = d.top_priority
    """
    params: list[Any] = []
    if team_id:
        q += " WHERE p.team_id = ?"
        params.append(team_id)
    q += " ORDER BY d.development_leverage_score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/overview")
def overview() -> dict:
    conn = get_conn()
    meta_teams = conn.execute("SELECT COUNT(*) c FROM teams").fetchone()["c"]
    meta_players = conn.execute("SELECT COUNT(*) c FROM players").fetchone()["c"]

    # Aggregate top team needs across dataset
    need_cols = [
        "shooting_need", "ball_security_need", "defensive_rebounding_need",
        "foul_discipline_need", "playmaking_need", "free_throw_need",
        "offensive_rebounding_need", "defensive_activity_need", "rim_pressure_need",
    ]
    avgs = {}
    for col in need_cols:
        r = conn.execute(f"SELECT AVG({col}) as v FROM team_need_scores").fetchone()
        avgs[col] = round(r["v"], 1) if r["v"] else 0

    top_needs = sorted(
        [{"category": k.replace("_need", ""), "score": v} for k, v in avgs.items()],
        key=lambda x: x["score"],
        reverse=True,
    )

    leverage = conn.execute(
        """
        SELECT p.player_name, t.team_name, d.development_leverage_score, d.top_priority
        FROM development_leverage_scores d
        JOIN players p ON d.player_id = p.player_id
        JOIN teams t ON p.team_id = t.team_id
        ORDER BY d.development_leverage_score DESC LIMIT 10
        """
    ).fetchall()

    featured = conn.execute(
        "SELECT * FROM team_need_scores WHERE team_id = ?",
        (FEATURED_TEAM_ID,),
    ).fetchone()
    conn.close()

    manifest_path = DB_PATH.parent / "data_manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        import json
        manifest = json.loads(manifest_path.read_text())

    return {
        "teams_count": meta_teams,
        "players_count": meta_players,
        "top_team_needs": top_needs,
        "top_leverage_players": rows_to_dicts(leverage),
        "featured_team_id": FEATURED_TEAM_ID,
        "featured_team_needs": dict(featured) if featured else {},
        "roster_projection_last_updated": manifest.get(
            "roster_projection_last_updated", "2026-05-28"
        ),
        "roster_status_warning": manifest.get("roster_status_warning", ""),
    }


@app.post("/api/simulate")
def simulate_impact(body: dict[str, Any]) -> dict:
    """Estimate projected impact from user-adjusted improvement sliders."""
    player_id = body.get("player_id")
    if not player_id:
        raise HTTPException(400, "player_id required")

    conn = get_conn()
    player = conn.execute("SELECT * FROM players WHERE player_id = ?", (player_id,)).fetchone()
    if not player:
        conn.close()
        raise HTTPException(404, "Player not found")
    team = conn.execute(
        "SELECT * FROM teams WHERE team_id = ?", (player["team_id"],)
    ).fetchone()
    priority_rows = conn.execute(
        """
        SELECT skill_category, player_improvement_opportunity
        FROM development_priority_scores WHERE player_id = ?
        """,
        (player_id,),
    ).fetchall()
    conn.close()

    p = dict(player)
    t = dict(team) if team else {}
    impacts = simulate_impacts_from_sliders(p, t, body)
    scenario = body.get("scenario", "manual")
    opportunity_by_skill = {
        row["skill_category"]: row["player_improvement_opportunity"] for row in priority_rows
    }
    if scenario == "suggested":
        impacts = apply_suggested_value_dampening(impacts, opportunity_by_skill)

    total = sum(impacts.values())

    return {
        "player_id": player_id,
        "impacts_by_skill": {k: round(v, 2) for k, v in impacts.items()},
        "total_projected_value": round(total, 2),
        "inputs": body,
        "scenario": scenario,
        "projection_engine": "unified",
        "calibration_source": "projection_calibration.json",
    }
