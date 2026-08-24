"""
Optional shot-location layer for DevelopmentIQ.

Official rim-location metrics (rim FG%, rim attempt rate) are only used when
shot_profile_source indicates tracked/official data — never from box-score estimates.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from models.player_advanced import (
    NO_GAP_DATA_OPPORTUNITY,
    confidence_from_coverage,
    gaps_for_column,
    opportunity_score,
    stat_coverage,
    stat_or_none,
    weighted_opportunity_components,
)

OFFICIAL_SHOT_SOURCES = frozenset(
    {"tracking", "official", "synergy", "sports_reference", "hoop_explorer"}
)
ESTIMATED_SOURCE = "estimated"


def _finite_number(value: Any, default: float = 0.0) -> float:
    """Coerce missing/NaN/inf to a finite default (pandas to_dict often yields NaN)."""
    try:
        if value is None or value == "":
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not np.isfinite(out):
        return default
    return out


SHOT_PROFILE_COLUMNS = [
    "shot_profile_source",
    "rim_attempts",
    "rim_makes",
    "rim_fg_pct",
    "rim_attempt_rate",
    "midrange_attempts",
    "midrange_makes",
    "midrange_fg_pct",
    "midrange_attempt_rate",
    "corner_three_attempts",
    "corner_three_makes",
    "corner_three_pct",
    "corner_three_attempt_rate",
    "above_break_three_attempts",
    "above_break_three_makes",
    "above_break_three_pct",
    "above_break_three_attempt_rate",
    "assisted_rim_rate",
    "assisted_three_rate",
]

# Position priors for box-score estimates (notes only — not official rim data)
_RIM_SHARE_PRIOR = {"G": 0.22, "F": 0.38, "C": 0.48}
_MID_SHARE_PRIOR = {"G": 0.28, "F": 0.32, "C": 0.22}


def _get(player: pd.Series | dict, col: str) -> Any:
    if isinstance(player, dict):
        return player.get(col)
    return player.get(col) if col in player.index else None


def player_three_point_attempt_rate(player: pd.Series | dict) -> float:
    """Season 3PA / FGA; 0 when no FGA."""
    tpar = stat_or_none(player, "three_point_attempt_rate")
    if tpar is not None:
        return float(tpar)
    fga = float(_get(player, "field_goal_attempts") or 0)
    tpa = float(_get(player, "three_point_attempts") or 0)
    return (tpa / fga) if fga > 0 else 0.0


def center_position_median_three_point_attempt_rate(players: pd.DataFrame) -> float:
    """Median 3PA rate among centers in the scored player pool."""
    if players is None or players.empty:
        return 0.0
    centers = players[
        players["position"].astype(str).str.strip().str.upper() == "C"
    ]
    if centers.empty:
        return 0.0
    rates = [player_three_point_attempt_rate(row) for _, row in centers.iterrows()]
    return float(np.median(rates)) if rates else 0.0


def center_shooting_volume_flags(
    player: pd.Series | dict,
    center_median_tpar: float,
) -> dict[str, bool]:
    """
    Center 3PT volume guardrails (validation-driven).
    - rim_only: season 3PA <= 5
    - low_volume: 3PA < 30 and 3PA rate below center-position median
    - stretch_eligible: 3PA >= 30 or 3PA rate >= center median
    """
    pos = str(_get(player, "position") or "F").strip().upper()[:1]
    if pos != "C":
        return {
            "is_center": False,
            "rim_only": False,
            "low_volume": False,
            "stretch_eligible": True,
        }
    tpa = int(_get(player, "three_point_attempts") or 0)
    tpar = player_three_point_attempt_rate(player)
    med = float(center_median_tpar or 0.0)
    return {
        "is_center": True,
        "rim_only": tpa <= 5,
        "low_volume": tpa < 30 and tpar < med,
        "stretch_eligible": tpa >= 30 or tpar >= med,
    }


CENTER_LOW_VOLUME_SHOOTING_EXPLANATION = (
    "Low-volume centers are not treated as spacing-development projects unless they have "
    "enough three-point volume to make that pathway realistic. Team shooting need alone is "
    "not enough to make Three-Point Shooting an actionable priority for a rim-only big."
)


def shot_profile_source(player: pd.Series | dict) -> str | None:
    src = _get(player, "shot_profile_source")
    if src is None or (isinstance(src, float) and np.isnan(src)):
        return None
    return str(src).strip().lower() or None


def has_rim_location_data(player: pd.Series | dict) -> bool:
    """True only when official/tracked rim splits exist."""
    src = shot_profile_source(player)
    if src not in OFFICIAL_SHOT_SOURCES:
        return False
    rim = _get(player, "rim_attempts")
    if rim is None or (isinstance(rim, float) and np.isnan(rim)):
        rim = _get(player, "rim_attempt_rate")
    return rim is not None and not (isinstance(rim, float) and np.isnan(rim))


def rim_pressure_skill_label(player: pd.Series | dict | None = None) -> str:
    if player is not None and has_rim_location_data(player):
        return "Rim Pressure / Finishing"
    return "Rim Pressure / Finishing (proxy)"


def has_any_shot_profile(player: pd.Series | dict) -> bool:
    for col in SHOT_PROFILE_COLUMNS:
        if col == "shot_profile_source":
            continue
        v = _get(player, col)
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            return True
    return False


def estimate_shot_profile_from_boxscore(player: dict[str, Any]) -> dict[str, Any]:
    """
    Derive rough zone mix from FGA/3PA for shot-selection notes only.
    Sets shot_profile_source='estimated' — does NOT enable official rim formulas.
    """
    g = max(int(_finite_number(player.get("games_played"), 1)), 1)
    fga = _finite_number(player.get("field_goal_attempts"), 0.0)
    if fga <= 0:
        tpar = _finite_number(player.get("three_point_attempt_rate"), 0.0)
        tpa = _finite_number(player.get("three_point_attempts"), 0.0)
        fga = tpa / tpar if tpar > 0.05 else max(tpa * 2.2, 50)
    tpa = _finite_number(player.get("three_point_attempts"), 0.0)
    if tpa <= 0:
        tpar = _finite_number(player.get("three_point_attempt_rate"), 0.0)
        tpa = fga * tpar
    two_a = max(fga - tpa, 0)
    pos = str(player.get("position", "F") or "F").strip().upper()[:1]
    if pos not in _RIM_SHARE_PRIOR:
        pos = "F"
    rim_share = _RIM_SHARE_PRIOR[pos]
    mid_share = _MID_SHARE_PRIOR[pos]
    rim_a = two_a * rim_share
    mid_a = two_a * mid_share
    tpa_pg = tpa / g
    fga_pg = fga / g
    rim_pg = rim_a / g
    mid_pg = mid_a / g
    tp_pct = _finite_number(player.get("three_point_pct"), 0.33)
    two_pct = _finite_number(player.get("two_point_pct"), 0.5)
    rim_fg = min(0.72, max(0.35, two_pct * 1.05))
    mid_fg = min(0.55, max(0.30, two_pct * 0.92))
    corner_share = 0.35 if pos == "G" else 0.28
    corner_tpa = tpa * corner_share
    ab_tpa = tpa - corner_tpa
    return {
        "shot_profile_source": ESTIMATED_SOURCE,
        "rim_attempts": int(round(rim_a)),
        "rim_makes": int(round(rim_a * rim_fg)),
        "rim_fg_pct": round(rim_fg, 3),
        "rim_attempt_rate": round(rim_pg / max(fga_pg, 0.1), 3),
        "midrange_attempts": int(round(mid_a)),
        "midrange_makes": int(round(mid_a * mid_fg)),
        "midrange_fg_pct": round(mid_fg, 3),
        "midrange_attempt_rate": round(mid_pg / max(fga_pg, 0.1), 3),
        "corner_three_attempts": int(round(corner_tpa)),
        "corner_three_pct": round(tp_pct * 1.02, 3),
        "corner_three_attempt_rate": round((corner_tpa / g) / max(fga_pg, 0.1), 3),
        "above_break_three_attempts": int(round(ab_tpa)),
        "above_break_three_pct": round(tp_pct * 0.98, 3),
        "above_break_three_attempt_rate": round((ab_tpa / g) / max(fga_pg, 0.1), 3),
    }


def enrich_player_shot_profile(player: dict[str, Any], *, estimate_if_missing: bool = True) -> dict[str, Any]:
    out = dict(player)
    src = shot_profile_source(out)
    if src in OFFICIAL_SHOT_SOURCES:
        return out
    if has_any_shot_profile(out) or not estimate_if_missing:
        return out
    if _finite_number(out.get("field_goal_attempts"), 0.0) <= 0 and _finite_number(
        out.get("three_point_attempts"), 0.0
    ) <= 0:
        return out
    est = estimate_shot_profile_from_boxscore(out)
    for k, v in est.items():
        if out.get(k) is None or (isinstance(out.get(k), float) and np.isnan(out.get(k))):
            out[k] = v
    return out


def shooting_opportunity_with_profile(
    player: pd.Series,
    pos_peers: pd.DataFrame,
    field: pd.DataFrame,
    field_avg: dict[str, float],
    *,
    scale_gaps,
) -> float:
    gaps = gaps_for_column(player, pos_peers, field, "three_point_pct", field_avg)
    gaps.extend(gaps_for_column(player, pos_peers, field, "efg_pct", field_avg))
    tpar = stat_or_none(player, "three_point_attempt_rate")
    if tpar is None:
        fga = float(player.get("field_goal_attempts", 0) or 0)
        tpa = float(player.get("three_point_attempts", 0) or 0)
        if fga > 0:
            tpar = tpa / fga
    if tpar is not None and "three_point_attempt_rate" in pos_peers.columns:
        med = float(pos_peers["three_point_attempt_rate"].median())
        if tpar < med * 0.65:
            gaps = scale_gaps(gaps, 0.55)
        elif tpar >= med * 1.15:
            gaps = scale_gaps(gaps, 1.05)
    corner = stat_or_none(player, "corner_three_attempt_rate")
    above = stat_or_none(player, "above_break_three_attempt_rate")
    if corner is not None and "corner_three_attempt_rate" in pos_peers.columns:
        med_c = float(pos_peers["corner_three_attempt_rate"].dropna().median())
        if corner < med_c * 0.7 and tpar and tpar > 0.2:
            gaps.append(min(40.0, (med_c - corner) / max(med_c, 0.01) * 30))
    if above is not None and "above_break_three_attempt_rate" in pos_peers.columns:
        med_a = float(pos_peers["above_break_three_attempt_rate"].dropna().median())
        tp = stat_or_none(player, "three_point_pct") or 0.0
        if above >= med_a * 1.2 and tp < float(pos_peers["three_point_pct"].median()):
            gaps.append(min(35.0, (above - med_a) / max(med_a, 0.01) * 25))
    if int(player.get("three_point_attempts", 0) or 0) < 30:
        gaps = scale_gaps(gaps, 0.5)
    return opportunity_score(
        gaps,
        core_columns=["three_point_pct", "efg_pct"],
        player=player,
    )


def rim_pressure_opportunity_with_profile(
    player: pd.Series,
    pos_peers: pd.DataFrame,
    field: pd.DataFrame,
    field_avg: dict[str, float],
) -> float:
    if has_rim_location_data(player):
        tracked_cols = ("rim_fg_pct", "rim_attempt_rate", "free_throw_rate", "ts_pct")
        components = [
            (gaps_for_column(player, pos_peers, field, col, field_avg), w)
            for col, w in (
                ("rim_fg_pct", 0.35),
                ("rim_attempt_rate", 0.25),
                ("free_throw_rate", 0.20),
                ("ts_pct", 0.20),
            )
        ]
        raw = weighted_opportunity_components(components)
        if raw <= NO_GAP_DATA_OPPORTUNITY:
            return NO_GAP_DATA_OPPORTUNITY
        return raw * confidence_from_coverage(stat_coverage(player, list(tracked_cols)))
    proxy_cols = ("free_throw_rate", "two_point_pct", "ts_pct", "efg_pct")
    components = [
        (gaps_for_column(player, pos_peers, field, "free_throw_rate", field_avg), 0.40),
        (gaps_for_column(player, pos_peers, field, "two_point_pct", field_avg), 0.25),
        (gaps_for_column(player, pos_peers, field, "ts_pct", field_avg), 0.20),
        (gaps_for_column(player, pos_peers, field, "efg_pct", field_avg), 0.15),
    ]
    raw = weighted_opportunity_components(components)
    if raw <= NO_GAP_DATA_OPPORTUNITY:
        return NO_GAP_DATA_OPPORTUNITY
    return raw * confidence_from_coverage(stat_coverage(player, list(proxy_cols)))


def free_throw_opportunity_with_profile(
    player: pd.Series,
    pos_peers: pd.DataFrame,
    field: pd.DataFrame,
    field_avg: dict[str, float],
    *,
    scale_gaps,
) -> float:
    gaps = gaps_for_column(player, pos_peers, field, "free_throw_pct", field_avg)
    ftr = stat_or_none(player, "free_throw_rate")
    fta = int(player.get("free_throw_attempts", 0) or 0)
    rim_r = stat_or_none(player, "rim_attempt_rate")
    if ftr is not None and "free_throw_rate" in pos_peers.columns:
        med_ftr = float(pos_peers["free_throw_rate"].median())
        med_ft = float(pos_peers["free_throw_pct"].median())
        ft_pct = float(player.get("free_throw_pct", 0.7) or 0.7)
        if ftr >= med_ftr and ft_pct < med_ft:
            gaps.append(min(100.0, (ftr / max(med_ftr, 0.01)) * 35))
        if rim_r is not None and rim_r >= med_ftr * 0.9 and ft_pct < med_ft:
            gaps.append(min(30.0, 15 + (ftr - med_ftr) * 40))
    if fta < 40:
        gaps = scale_gaps(gaps, 0.6)
    elif fta < 80 and ftr is not None:
        med_ftr = float(pos_peers["free_throw_rate"].median()) if len(pos_peers) else 0.32
        if ftr < med_ftr * 0.85:
            gaps = scale_gaps(gaps, 0.75)
    return opportunity_score(
        gaps,
        core_columns=["free_throw_pct"],
        player=player,
    )


def shot_selection_notes(player: pd.Series | dict) -> list[str]:
    """Context lines appended to explanations — not a separate skill."""
    if not has_any_shot_profile(player):
        return []
    src = shot_profile_source(player)
    prefix = "Estimated shot mix: " if src == ESTIMATED_SOURCE else "Shot profile: "
    notes: list[str] = []
    rim_r = stat_or_none(player, "rim_attempt_rate")
    rim_fg = stat_or_none(player, "rim_fg_pct")
    mid_r = stat_or_none(player, "midrange_attempt_rate")
    mid_fg = stat_or_none(player, "midrange_fg_pct")
    corner_r = stat_or_none(player, "corner_three_attempt_rate")
    tpar = stat_or_none(player, "three_point_attempt_rate")
    tp = stat_or_none(player, "three_point_pct")

    if mid_r is not None and mid_r >= 0.28:
        if mid_fg is not None and mid_fg < 0.38:
            notes.append(f"{prefix}high midrange volume ({mid_r * 100:.0f}% of FGA) with poor mid efficiency.")
        else:
            notes.append(f"{prefix}heavy midrange diet ({mid_r * 100:.0f}% of FGA) — shot selection context.")
    if rim_r is not None and rim_r < 0.22 and (tp or 0) < 0.34:
        notes.append(f"{prefix}low rim attempt rate — spacing/finishing pressure more about getting to the paint than missing bunnies.")
    if rim_r is not None and rim_fg is not None:
        if rim_r >= 0.35 and rim_fg < 0.52:
            notes.append(f"{prefix}finishing concern: {rim_fg * 100:.0f}% rim FG on {rim_r * 100:.0f}% rim attempt rate.")
        elif rim_fg >= 0.58 and rim_r < 0.28:
            notes.append(f"{prefix}efficient rim finisher ({rim_fg * 100:.0f}% rim FG) but low rim frequency — pressure is getting there, not touch.")
    if corner_r is not None and corner_r < 0.08 and tpar is not None and tpar > 0.35:
        notes.append(f"{prefix}low corner-three rate — role is more above-the-break or pull-up than stationary spacer.")
    if tpar is not None and tpar > 0.45 and tp is not None and tp < 0.33:
        notes.append(f"{prefix}difficult three-point volume ({tpar * 100:.0f}% 3PA rate at {tp * 100:.0f}% 3P%).")
    if has_rim_location_data(player) and not notes:
        notes.append(f"{prefix}tracked rim and zone splits inform this recommendation.")
    return notes[:2]


def append_shot_notes(parts: list[str], player: pd.Series, *, profile_note: bool = True) -> None:
    if profile_note and has_any_shot_profile(player):
        if has_rim_location_data(player):
            parts.append(
                "Shot-profile data separates finishing, shot selection, and spacing role."
            )
        else:
            parts.append(
                "Shot-profile notes use estimated zone mix where official tracking is unavailable; "
                "rim finishing uses public efficiency proxies."
            )
    for note in shot_selection_notes(player):
        parts.append(note)


def team_rim_pressure_need_boost(team: pd.Series) -> float | None:
    """Extra 0–15 need points when team shot profile columns exist."""
    rim_r = team.get("team_rim_attempt_rate")
    rim_fg = team.get("team_rim_fg_pct")
    if rim_r is None or (isinstance(rim_r, float) and np.isnan(rim_r)):
        return None
    boost = 0.0
    if float(rim_r) < 0.30:
        boost += 8
    if rim_fg is not None and float(rim_fg) < 0.50:
        boost += 7
    return min(15.0, boost)


def team_shooting_need_boost(team: pd.Series) -> float | None:
    tpr = team.get("team_three_point_attempt_rate")
    corner_allowed = team.get("opp_corner_three_rate_allowed")
    boost = 0.0
    if tpr is not None and not (isinstance(tpr, float) and np.isnan(tpr)):
        if float(tpr) < 0.32:
            boost += 6
    if corner_allowed is not None and float(corner_allowed) > 0.38:
        boost += 5
    return min(12.0, boost) if boost > 0 else None
