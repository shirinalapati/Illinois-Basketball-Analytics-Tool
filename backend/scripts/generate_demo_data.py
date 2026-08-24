"""
Generate realistic demo college basketball data for DevelopmentIQ.
Data is labeled DEMO — structured to mirror BartTorvik / Sports Reference style stats.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from teams_universe import TEAMS_SPEC

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FIRST_NAMES = [
    "Marcus", "Jayden", "Tyler", "Brandon", "Derek", "Chris", "Jordan", "Kyle",
    "Nate", "Elijah", "Cameron", "Devin", "Malik", "Andre", "Ryan", "Luke",
    "Ben", "Noah", "Ethan", "Mason", "Cole", "Jake", "Alex", "David", "Kevin",
]
LAST_NAMES = [
    "Johnson", "Williams", "Brown", "Davis", "Miller", "Wilson", "Moore",
    "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin",
    "Thompson", "Garcia", "Robinson", "Clark", "Lewis", "Walker", "Hall",
    "Allen", "Young", "King", "Wright", "Scott", "Green", "Adams", "Baker",
]
POSITIONS = ["G", "G", "G", "F", "F", "F", "C", "C"]
CLASS_YEARS = ["Fr", "So", "Jr", "Sr"]


def _team_profile(tid: str) -> dict:
    """Assign team-level tendencies — default program gets illustrative weaknesses."""
    base = {
        "pace": np.random.uniform(66, 72),
        "offensive_rating": np.random.uniform(102, 118),
        "defensive_rating": np.random.uniform(92, 108),
        "efg_pct": np.random.uniform(0.47, 0.55),
        "three_point_rate": np.random.uniform(0.32, 0.45),
        "turnover_rate": np.random.uniform(0.14, 0.20),
        "offensive_rebound_rate": np.random.uniform(0.26, 0.34),
        "defensive_rebound_rate": np.random.uniform(0.26, 0.34),
        "free_throw_rate": np.random.uniform(0.28, 0.38),
        "assist_rate": np.random.uniform(0.48, 0.58),
        "block_rate": np.random.uniform(0.07, 0.12),
        "steal_rate": np.random.uniform(0.08, 0.11),
        "foul_rate": np.random.uniform(0.18, 0.26),
    }
    if tid == "san_jose_state":
        base.update({
            "defensive_rebound_rate": 0.265,
            "turnover_rate": 0.178,
            "foul_rate": 0.248,
            "defensive_rating": 98.5,
            "offensive_rating": 112.0,
            "three_point_rate": 0.38,
            "efg_pct": 0.512,
        })
    elif tid in ("purdue", "houston"):
        base["defensive_rating"] = np.random.uniform(88, 94)
        base["defensive_rebound_rate"] = np.random.uniform(0.30, 0.34)
    return base


# 2025-26 season (end-year convention: 2026 in database, displayed as 2025-26)
SEASON_YEAR = 2026
SEASON_LABEL = "2025-26"


def generate_teams(season: int = SEASON_YEAR) -> pd.DataFrame:
    rows = []
    for tid, name, conf in TEAMS_SPEC:
        prof = _team_profile(tid)
        rows.append({
            "team_id": tid,
            "team_name": name,
            "conference": conf,
            "season": season,
            "games_played": 32,
            "data_source": "DEMO — modeled on public BartTorvik/Sports Reference style metrics",
            **prof,
        })
    return pd.DataFrame(rows)


def generate_players(teams: pd.DataFrame) -> pd.DataFrame:
    rows = []
    player_idx = 0
    for _, team in teams.iterrows():
        tid = team["team_id"]
        n_players = random.randint(8, 11)
        for i in range(n_players):
            pos = random.choice(POSITIONS)
            mpg = np.random.uniform(8, 34)
            if i < 7:
                mpg = max(mpg, np.random.uniform(12, 32))
            games = int(team["games_played"] * np.random.uniform(0.5, 1.0))
            minutes = mpg * games
            if minutes < 250 and mpg < 10:
                continue
            if mpg < 10 and minutes < 250:
                continue

            usage = np.random.uniform(0.12, 0.28)
            if pos == "G":
                usage = np.random.uniform(0.16, 0.30)
            ppg = np.random.uniform(4, 18) * (mpg / 28)

            efg = np.random.uniform(0.42, 0.58)
            ts = efg + np.random.uniform(-0.02, 0.06)
            tp_pct = np.random.uniform(0.28, 0.42)
            tp_att = int(mpg * games * np.random.uniform(0.15, 0.45))
            ft_pct = np.random.uniform(0.62, 0.85)
            ft_att = int(mpg * games * np.random.uniform(0.08, 0.25))
            tov_r = np.random.uniform(0.10, 0.22)
            ast_r = np.random.uniform(0.05, 0.25)
            oreb_r = np.random.uniform(0.02, 0.14)
            dreb_r = np.random.uniform(0.08, 0.22)
            stl_r = np.random.uniform(0.01, 0.04)
            blk_r = np.random.uniform(0.005, 0.06)
            foul_r = np.random.uniform(0.02, 0.07)

            if tid == "san_jose_state" and i == 2:
                dreb_r = 0.09
                foul_r = 0.062
                tp_pct = 0.29
                mpg = 26.4
            if tid == "san_jose_state" and i == 4:
                tov_r = 0.19
                mpg = 24.1

            fname = random.choice(FIRST_NAMES)
            lname = random.choice(LAST_NAMES)
            player_idx += 1
            rows.append({
                "player_id": f"{tid}_{player_idx}",
                "player_name": f"{fname} {lname}",
                "team_id": tid,
                "position": pos,
                "class_year": random.choice(CLASS_YEARS),
                "games_played": games,
                "minutes": round(minutes, 1),
                "mpg": round(mpg, 1),
                "usage_rate": round(usage, 3),
                "points": round(ppg * games, 1),
                "ppg": round(ppg, 1),
                "efg_pct": round(efg, 3),
                "ts_pct": round(ts, 3),
                "three_point_attempts": tp_att,
                "three_point_pct": round(tp_pct, 3),
                "free_throw_attempts": ft_att,
                "free_throw_pct": round(ft_pct, 3),
                "turnover_rate": round(tov_r, 3),
                "assist_rate": round(ast_r, 3),
                "offensive_rebound_rate": round(oreb_r, 3),
                "defensive_rebound_rate": round(dreb_r, 3),
                "steal_rate": round(stl_r, 3),
                "block_rate": round(blk_r, 3),
                "foul_rate": round(foul_r, 3),
                "data_source": "DEMO",
            })
    df = pd.DataFrame(rows)
    # Filter rotation players
    df = df[(df["mpg"] >= 10) | (df["minutes"] >= 250)]
    return df


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    teams = generate_teams()
    players = generate_players(teams)
    teams.to_csv(DATA_DIR / "teams_demo.csv", index=False)
    players.to_csv(DATA_DIR / "players_demo.csv", index=False)
    meta = {
        "label": "DEMO DATA",
        "description": "Synthetic 2025-26 season dataset mirroring public CBB stat schema. Replace with BartTorvik/Sports Reference 2025-26 ingestion for production.",
        "season": SEASON_YEAR,
        "season_label": SEASON_LABEL,
        "teams_count": len(teams),
        "players_count": len(players),
        "sources_intended": ["BartTorvik", "Sports Reference", "NCAA public stats"],
    }
    with open(DATA_DIR / "data_manifest.json", "w") as f:
        json.dump(meta, f, indent=2)
    print(f"Generated {len(teams)} teams, {len(players)} rotation players → {DATA_DIR}")


if __name__ == "__main__":
    main()
