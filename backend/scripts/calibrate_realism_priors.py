"""
Calibrate Improvement Realism from year-over-year player stat movement.

Matches returning players (same player_id / same school) between:
  - backend/data/sr_cache_prior/  (2024-25)
  - backend/data/sr_cache/        (2025-26)

Median absolute change per skill bucket → normalized 20–100 realism scores.
Writes backend/data/realism_calibration.json and prints REALISM_DEFAULTS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.scoring import REALISM_DEFAULTS, SKILL_CATEGORIES  # noqa: E402

# Per-game / rate columns used for YoY (rates alone under-report rebounding & defense)
SKILL_YOY_COLS: dict[str, tuple[str, ...]] = {
    "shooting": ("three_point_pct", "efg_pct"),
    "free_throw": ("free_throw_pct",),
    "ball_security": ("turnover_rate", "tov_per_game"),
    "offensive_rebounding": ("orb_per_game",),
    "defensive_rebounding": ("drb_per_game",),
    "foul_discipline": ("pf_per_game",),
    "playmaking": ("assist_rate", "ast_per_game"),
    "defensive_activity": ("stl_per_game", "blk_per_game"),
    "rim_pressure": ("ts_pct", "efg_pct"),
}

DATA_DIR = ROOT / "data"
CURRENT_CACHE = DATA_DIR / "sr_cache"
PRIOR_CACHE = DATA_DIR / "sr_cache_prior"
OUT_PATH = DATA_DIR / "realism_calibration.json"

MIN_MPG = 10.0
FLOOR = 20
CEILING = 100


def load_players_from_cache(cache_dir: Path) -> pd.DataFrame:
    rows: list[dict] = []
    if not cache_dir.exists():
        return pd.DataFrame()
    for path in sorted(cache_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        for p in payload.get("players", []):
            rows.append(p)
    return pd.DataFrame(rows)


def skill_yoy_delta(row_cur: pd.Series, row_prior: pd.Series, skill: str) -> float | None:
    cols = SKILL_YOY_COLS[skill]
    deltas = []
    for col in cols:
        if col not in row_cur.index or col not in row_prior.index:
            continue
        a, b = row_cur[col], row_prior[col]
        if pd.isna(a) or pd.isna(b):
            continue
        deltas.append(abs(float(a) - float(b)))
    return float(np.mean(deltas)) if deltas else None


def normalize_scores(raw: dict[str, float]) -> dict[str, int]:
    """Rank skills by median YoY movement, spread evenly on 20–100."""
    ordered = sorted(SKILL_CATEGORIES, key=lambda s: raw[s])
    n = len(ordered)
    return {
        s: int(round(FLOOR + i / max(n - 1, 1) * (CEILING - FLOOR)))
        for i, s in enumerate(ordered)
    }


def calibrate() -> tuple[dict[str, int], dict]:
    prior = load_players_from_cache(PRIOR_CACHE)
    current = load_players_from_cache(CURRENT_CACHE)
    if prior.empty or current.empty:
        raise RuntimeError(
            "Need both sr_cache_prior and sr_cache. Run: python ingest_prior_season.py"
        )

    prior = prior[(prior["mpg"] >= MIN_MPG) | (prior["minutes"] >= 250)]
    current = current[(current["mpg"] >= MIN_MPG) | (current["minutes"] >= 250)]

    cur = current.set_index("player_id")
    pr = prior.set_index("player_id")
    common = cur.index.intersection(pr.index)

    skill_medians: dict[str, float] = {}
    skill_samples: dict[str, int] = {}
    matched = 0

    pair_deltas: dict[str, list[float]] = {s: [] for s in SKILL_CATEGORIES}

    for pid in common:
        # player_id = {team_id}_{name}; portal movers get a new id at a new school — skip them
        if cur.loc[pid, "team_id"] != pr.loc[pid, "team_id"]:
            continue
        matched += 1
        for skill in SKILL_CATEGORIES:
            d = skill_yoy_delta(cur.loc[pid], pr.loc[pid], skill)
            if d is not None:
                pair_deltas[skill].append(d)

    for skill in SKILL_CATEGORIES:
        deltas = pair_deltas[skill]
        skill_samples[skill] = len(deltas)
        skill_medians[skill] = float(np.median(deltas)) if deltas else 0.0

    realism = normalize_scores(skill_medians)

    meta = {
        "matched_players": matched,
        "match_rule": (
            "Same school only: player_id includes team_id, so portal/transfer "
            "players (even between two of the 103 teams) are excluded. Both seasons "
            "must be at a school in the 103-team ingest."
        ),
        "transfers_included": False,
        "prior_season": "2024-25",
        "current_season": "2025-26",
        "method": (
            "median absolute YoY change per skill bucket; "
            "skills ranked by median movement, scores spread 20-100"
        ),
        "median_abs_change": {k: round(v, 5) for k, v in skill_medians.items()},
        "samples_per_skill": skill_samples,
        "realism_scores": realism,
    }
    return realism, meta


def main() -> None:
    realism, meta = calibrate()
    OUT_PATH.write_text(json.dumps(meta, indent=2))
    print(f"Wrote {OUT_PATH}")
    print(f"Matched returning players: {meta['matched_players']}")
    print("\nREALISM_DEFAULTS = {")
    for skill in SKILL_CATEGORIES:
        med = meta["median_abs_change"][skill]
        n = meta["samples_per_skill"][skill]
        print(f'    "{skill}": {realism[skill]},  # median |Δ|={med}, n={n}')
    print("}")


if __name__ == "__main__":
    main()
