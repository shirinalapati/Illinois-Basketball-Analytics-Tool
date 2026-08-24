"""
Pre-submission validation: SR team stat parity, need-direction sanity, position priorities.

Usage:
  python scripts/validate_dataset.py
  python scripts/validate_dataset.py --write-report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parent))

from ingest_sports_reference import DATA_DIR, _load_cache
from models.scoring import ScoringEngine, SKILL_CATEGORIES

VALIDATION_TEAMS = [
    "san_jose_state",
    "duke",
    "purdue",
    "houston",
    "kentucky",
    "uconn",
    "auburn",
    "gonzaga",
    "alabama",
    "michigan_state",
]

STAT_COLS = [
    ("offensive_rating", "offensive_rating", None),
    ("defensive_rating", "defensive_rating", None),
    ("pace", "pace", None),
    ("efg_pct", "efg_pct", None),
    ("turnover_rate", "turnover_rate", None),
    ("offensive_rebound_rate", "offensive_rebound_rate", None),
    ("defensive_rebound_rate", "defensive_rebound_rate", None),
    ("free_throw_rate", "free_throw_rate", None),
    ("assist_rate", "assist_rate", None),
]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def validate_team_stats_vs_sr(teams: pd.DataFrame) -> list[str]:
    lines = ["## 1. Team stats vs Sports Reference cache", ""]
    ok = 0
    fail = 0
    for tid in VALIDATION_TEAMS:
        cached = _load_cache(tid)
        if not cached or "team" not in cached:
            lines.append(f"- **{tid}**: MISSING SR cache")
            fail += 1
            continue
        sr = cached["team"]
        app_row = teams[teams["team_id"] == tid]
        if app_row.empty:
            lines.append(f"- **{tid}**: not in teams_demo.csv")
            fail += 1
            continue
        app = app_row.iloc[0]
        mismatches = []
        for label, col, tol in STAT_COLS:
            sr_v = float(sr.get(col, 0) or 0)
            app_v = float(app.get(col, 0) or 0)
            t = tol if tol is not None else (0.5 if col in ("offensive_rating", "defensive_rating", "pace") else 0.002)
            if abs(sr_v - app_v) > t:
                mismatches.append(f"{label} SR={sr_v:.4f} app={app_v:.4f}")
        if mismatches:
            lines.append(f"- **{tid}**: MISMATCH — " + "; ".join(mismatches))
            fail += 1
        else:
            lines.append(
                f"- **{tid}**: OK (ORtg {app['offensive_rating']:.1f}, "
                f"TOV% {_pct(app['turnover_rate'])}, ORB% {_pct(app['offensive_rebound_rate'])}, "
                f"DRB% {_pct(app['defensive_rebound_rate'])})"
            )
            ok += 1
    lines.append("")
    lines.append(f"**Summary:** {ok}/{len(VALIDATION_TEAMS)} teams match SR cache exactly.")
    lines.append("")
    return lines


def validate_need_direction(teams: pd.DataFrame, needs: pd.DataFrame) -> list[str]:
    lines = ["## 2. Team need ranking direction", ""]
    merged = teams.merge(needs, on="team_id")

    checks = [
        (
            "High turnover rate → higher ball_security need",
            "turnover_rate",
            "ball_security_need",
            True,
        ),
        (
            "Low defensive rebound % → higher defensive_rebounding need",
            "defensive_rebound_rate",
            "defensive_rebounding_need",
            False,
        ),
        (
            "Low offensive rebound % → higher offensive_rebounding need",
            "offensive_rebound_rate",
            "offensive_rebounding_need",
            False,
        ),
        (
            "High foul rate → higher foul_discipline need",
            "foul_rate",
            "foul_discipline_need",
            True,
        ),
        (
            "Low assist rate → higher playmaking need",
            "assist_rate",
            "playmaking_need",
            False,
        ),
    ]

    for label, stat_col, need_col, higher_stat_means_higher_need in checks:
        sub = merged[[stat_col, need_col]].dropna()
        if len(sub) < 10:
            lines.append(f"- {label}: SKIP (insufficient data)")
            continue
        corr = sub[stat_col].corr(sub[need_col])
        if higher_stat_means_higher_need:
            ok = corr is not None and corr > 0.15
        else:
            ok = corr is not None and corr < -0.15
        flag = "OK" if ok else "CHECK"
        lines.append(f"- **{label}**: r={corr:.2f} [{flag}]")

    lines.append("")
    return lines


def validate_position_priorities(priorities: pd.DataFrame, leverage: pd.DataFrame, players: pd.DataFrame) -> list[str]:
    lines = ["## 3. Top priority by position (pool-wide)", ""]
    top = leverage.merge(players[["player_id", "position"]], on="player_id", how="left")

    for pos, label in [("G", "Guards"), ("F", "Wings"), ("C", "Bigs")]:
        sub = top[top["position"] == pos]
        if sub.empty:
            continue
        counts = sub["top_priority"].value_counts().head(5)
        lines.append(f"### {label} (n={len(sub)})")
        for skill, n in counts.items():
            lines.append(f"- {skill}: {n}")
        lines.append("")

    lines.append("### Spot checks")
    spot_players = [
        ("Milan Momcilovic", "iowa_state"),
        ("JT Toppin", "texas_tech"),
    ]
    for name, tid in spot_players:
        pid_guess = None
        p = players[(players["player_name"] == name) & (players["team_id"] == tid)]
        if p.empty:
            p = players[players["player_name"].str.contains(name.split()[-1], case=False, na=False)]
        if p.empty:
            lines.append(f"- **{name}**: not on roster (may be departed/draft)")
            continue
        pid = p.iloc[0]["player_id"]
        lev = leverage[leverage["player_id"] == pid]
        pri = priorities[priorities["player_id"] == pid].sort_values(
            "development_priority_score", ascending=False
        )
        top_p = lev.iloc[0]["top_priority"] if not lev.empty else "—"
        shoot_opp = pri[pri["skill_category"] == "shooting"]["player_improvement_opportunity"]
        shoot_opp_v = float(shoot_opp.iloc[0]) if len(shoot_opp) else None
        lines.append(
            f"- **{name}** ({p.iloc[0]['position']}, {p.iloc[0]['team_id']}): "
            f"top={top_p}, shooting opp={shoot_opp_v}"
        )
    lines.append("")

    orb_guards = top[(top["position"] == "G") & (top["top_priority"] == "offensive_rebounding")]
    lines.append(
        f"**Guards with top priority = offensive_rebounding:** {len(orb_guards)} / "
        f"{len(top[top['position'] == 'G'])}"
    )
    lines.append("")
    return lines


def validate_kentucky_roster(players: pd.DataFrame) -> list[str]:
    lines = ["## 4. Roster sanity (Kentucky)", ""]
    ky = players[players["team_id"] == "kentucky"]["player_name"].tolist()
    lines.append(f"- Kentucky rotation ({len(ky)}): {', '.join(sorted(ky))}")
    ab = players[players["player_name"].str.contains("Aberdeen", case=False, na=False)]
    if ab.empty:
        lines.append("- Denzel Aberdeen: not in database")
    else:
        for _, r in ab.iterrows():
            lines.append(f"- Denzel Aberdeen: **{r['team_id']}** ({r['player_id']})")
    lines.append("")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    teams = pd.read_csv(DATA_DIR / "teams_demo.csv")
    players = pd.read_csv(DATA_DIR / "players_demo.csv")
    players = players[(players["mpg"] >= 10) | (players["minutes"] >= 250)]

    engine = ScoringEngine(teams, players)
    results = engine.run_all()
    needs = results["team_need_scores"]
    priorities = results["development_priority_scores"]
    leverage = results["development_leverage_scores"]

    report: list[str] = ["# DevelopmentIQ validation report", ""]
    report.extend(validate_team_stats_vs_sr(teams))
    report.extend(validate_need_direction(teams, needs))
    report.extend(validate_position_priorities(priorities, leverage, players))
    report.extend(validate_kentucky_roster(players))

    text = "\n".join(report)
    print(text)

    if args.write_report:
        out = DATA_DIR / "validation_report.md"
        out.write_text(text)
        print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
