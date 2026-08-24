"""
Calibrate projected-impact improvement scenarios from YoY player movement.

Same matched sample as calibrate_realism_priors.py (same-school returners, 103 teams).
Uses 75th percentile of positive year-over-year gains (clipped to sane bounds) plus
p90 ceilings from the current-season pool.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from calibrate_realism_priors import (  # noqa: E402
    CURRENT_CACHE,
    MIN_MPG,
    PRIOR_CACHE,
    load_players_from_cache,
)

OUT_PATH = ROOT / "data" / "projection_calibration.json"

# (min, max) clips for calibrated increments
INCREMENT_BOUNDS = {
    "three_point_pct": (0.025, 0.05),
    "free_throw_pct": (0.04, 0.08),
    "ts_pct": (0.02, 0.045),
    "turnover_reduction_frac": (0.04, 0.12),
    "orb_per_game": (0.005, 0.025),
    "drb_per_game": (0.01, 0.04),
    "pf_reduction_frac": (0.05, 0.12),
    "ast_per_game": (0.02, 0.05),
    "stl_blk_per_game": (0.005, 0.025),
}

CEILING_BOUNDS = {
    "three_point_pct": (0.36, 0.42),
    "free_throw_pct": (0.78, 0.88),
    "ts_pct": (0.56, 0.65),
}


def _clip(val: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, val)))


def _matched_pairs() -> list[tuple[pd.Series, pd.Series]]:
    prior = load_players_from_cache(PRIOR_CACHE)
    current = load_players_from_cache(CURRENT_CACHE)
    prior = prior[(prior["mpg"] >= MIN_MPG) | (prior["minutes"] >= 250)]
    current = current[(current["mpg"] >= MIN_MPG) | (current["minutes"] >= 250)]
    cur = current.set_index("player_id")
    pr = prior.set_index("player_id")
    pairs = []
    for pid in cur.index.intersection(pr.index):
        if cur.loc[pid, "team_id"] == pr.loc[pid, "team_id"]:
            pairs.append((cur.loc[pid], pr.loc[pid]))
    return pairs


def p75_positive_improve(pairs: list, col: str, lower_is_better: bool = False) -> float:
    deltas = []
    for cur, prior in pairs:
        if col not in cur.index:
            continue
        a, b = float(cur[col]), float(prior[col])
        delta = (b - a) if lower_is_better else (a - b)
        if delta > 0:
            deltas.append(delta)
    if len(deltas) < 20:
        # fallback: median absolute change
        abs_d = [abs(float(cur[col]) - float(prior[col])) for cur, prior in pairs if col in cur.index]
        return float(np.median(abs_d)) if abs_d else 0.0
    return float(np.percentile(deltas, 75))


def p75_fractional_reduction(pairs: list, col: str) -> float:
    fracs = []
    for cur, prior in pairs:
        if col not in cur.index:
            continue
        p, c = float(prior[col]), float(cur[col])
        if p <= 0:
            continue
        if p > c:
            fracs.append((p - c) / p)
    if not fracs:
        return 0.08
    return float(np.percentile(fracs, 75))


def _p75_stl_blk_improve(pairs: list) -> float:
    deltas = []
    for cur, prior in pairs:
        c = float(cur.get("stl_per_game", 0)) + float(cur.get("blk_per_game", 0))
        p = float(prior.get("stl_per_game", 0)) + float(prior.get("blk_per_game", 0))
        if c > p:
            deltas.append(c - p)
    if len(deltas) < 20:
        return 0.01
    return float(np.percentile(deltas, 75))


def p90_current(pairs: list, col: str) -> float:
    vals = [float(cur[col]) for cur, _ in pairs if col in cur.index]
    return float(np.percentile(vals, 90)) if vals else 0.0


def calibrate() -> dict:
    pairs = _matched_pairs()
    if len(pairs) < 50:
        raise RuntimeError("Too few matched pairs for projection calibration")

    tov_red = p75_fractional_reduction(pairs, "turnover_rate")
    tov_red = _clip(tov_red, *INCREMENT_BOUNDS["turnover_reduction_frac"])

    pf_red = p75_fractional_reduction(pairs, "pf_per_game")
    pf_red = _clip(pf_red, *INCREMENT_BOUNDS["pf_reduction_frac"])

    scenario = {
        "shooting": {
            "three_point_pct_increment": _clip(
                p75_positive_improve(pairs, "three_point_pct"),
                *INCREMENT_BOUNDS["three_point_pct"],
            ),
            "three_point_pct_ceiling": _clip(
                p90_current(pairs, "three_point_pct"),
                *CEILING_BOUNDS["three_point_pct"],
            ),
        },
        "free_throw": {
            "free_throw_pct_increment": _clip(
                p75_positive_improve(pairs, "free_throw_pct"),
                *INCREMENT_BOUNDS["free_throw_pct"],
            ),
            "free_throw_pct_ceiling": _clip(
                p90_current(pairs, "free_throw_pct"),
                *CEILING_BOUNDS["free_throw_pct"],
            ),
        },
        "ball_security": {"turnover_reduction_fraction": tov_red},
        "rim_pressure": {
            "ts_pct_increment": _clip(
                p75_positive_improve(pairs, "ts_pct"),
                *INCREMENT_BOUNDS["ts_pct"],
            ),
            "ts_pct_ceiling": _clip(
                p90_current(pairs, "ts_pct"),
                *CEILING_BOUNDS["ts_pct"],
            ),
        },
        "defensive_rebounding": {
            "drb_per_game_increment": _clip(
                p75_positive_improve(pairs, "drb_per_game"),
                *INCREMENT_BOUNDS["drb_per_game"],
            ),
        },
        "offensive_rebounding": {
            "orb_per_game_increment": _clip(
                p75_positive_improve(pairs, "orb_per_game"),
                *INCREMENT_BOUNDS["orb_per_game"],
            ),
        },
        "foul_discipline": {"foul_reduction_fraction": pf_red},
        "playmaking": {
            "ast_per_game_increment": _clip(
                p75_positive_improve(pairs, "ast_per_game"),
                *INCREMENT_BOUNDS["ast_per_game"],
            ),
        },
        "defensive_activity": {
            "stl_blk_per_game_increment": _clip(
                _p75_stl_blk_improve(pairs),
                *INCREMENT_BOUNDS["stl_blk_per_game"],
            ),
        },
        "point_values": {
            "second_chance_def_reb": 1.1,
            "second_chance_off_reb": 1.15,
            "assist_to_points": 1.5,
            "activity_to_points": 1.2,
            "foul_proxy": 0.7,
            "rim_fga_per_min": 0.35,
            "rim_efficiency_mult": 0.8,
        },
    }

    return {
        "matched_players": len(pairs),
        "prior_season": "2024-25",
        "current_season": "2025-26",
        "method": (
            "75th percentile of positive YoY improvement among same-school returners, "
            "clipped to bounds; ceilings from p90 of current-season stats"
        ),
        "scenario": scenario,
    }


def main() -> None:
    payload = calibrate()
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT_PATH}")
    print(f"Matched players: {payload['matched_players']}")
    print(json.dumps(payload["scenario"], indent=2))


if __name__ == "__main__":
    main()
