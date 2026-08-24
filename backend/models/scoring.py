"""
DevelopmentIQ scoring engine.
Computes team needs, player opportunities, development priorities, and leverage scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SKILL_CATEGORIES = [
    "shooting",
    "free_throw",
    "ball_security",
    "defensive_rebounding",
    "offensive_rebounding",
    "foul_discipline",
    "playmaking",
    "defensive_activity",
    "rim_pressure",
]

SKILL_LABELS = {
    "shooting": "Three-Point Shooting",
    "free_throw": "Free Throw Shooting",
    "ball_security": "Ball Security",
    "defensive_rebounding": "Defensive Rebounding",
    "offensive_rebounding": "Offensive Rebounding",
    "foul_discipline": "Foul Discipline",
    "playmaking": "Playmaking",
    "defensive_activity": "Defensive Activity",
    "rim_pressure": "Rim Pressure / Finishing",
}

# Fixed per-skill scores for DPS (10% + 10%). Same for all players and teams.
# Realism: YoY calibration — see scripts/calibrate_realism_priors.py
# Impact: Dean Oliver four factors — see scripts/calibrate_impact_priors.py
_REALISM_FALLBACK = {
    "free_throw": 88,
    "ball_security": 82,
    "foul_discipline": 80,
    "defensive_rebounding": 65,
    "offensive_rebounding": 62,
    "shooting": 58,
    "rim_pressure": 60,
    "playmaking": 48,
    "defensive_activity": 45,
}


def _load_realism_defaults() -> dict[str, int]:
    cal_path = Path(__file__).resolve().parent.parent / "data" / "realism_calibration.json"
    if cal_path.exists():
        payload = json.loads(cal_path.read_text())
        scores = payload.get("realism_scores")
        if isinstance(scores, dict) and len(scores) >= len(SKILL_CATEGORIES):
            return {k: int(scores[k]) for k in SKILL_CATEGORIES}
    return dict(_REALISM_FALLBACK)


REALISM_DEFAULTS = _load_realism_defaults()

IMPACT_DEFAULTS = {
    "ball_security": 100,
    "shooting": 95,
    "rim_pressure": 93,
    "offensive_rebounding": 77,
    "defensive_rebounding": 50,
    "playmaking": 36,
    "defensive_activity": 31,
    "foul_discipline": 22,
    "free_throw": 20,
}

_PROJECTION_FALLBACK = {
    "shooting": {"three_point_pct_increment": 0.04, "three_point_pct_ceiling": 0.38},
    "free_throw": {"free_throw_pct_increment": 0.07, "free_throw_pct_ceiling": 0.80},
    "ball_security": {"turnover_reduction_fraction": 0.10},
    "rim_pressure": {"ts_pct_increment": 0.03, "ts_pct_ceiling": 0.58},
    "defensive_rebounding": {"drb_per_game_increment": 0.02},
    "offensive_rebounding": {"orb_per_game_increment": 0.02},
    "foul_discipline": {"foul_reduction_fraction": 0.10},
    "playmaking": {"ast_per_game_increment": 0.05},
    "defensive_activity": {"stl_blk_per_game_increment": 0.01},
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


def _load_projection_scenario() -> dict:
    path = Path(__file__).resolve().parent.parent / "data" / "projection_calibration.json"
    if path.exists():
        payload = json.loads(path.read_text())
        scenario = payload.get("scenario")
        if isinstance(scenario, dict) and "shooting" in scenario:
            return scenario
    return _PROJECTION_FALLBACK


PROJECTION_SCENARIO = _load_projection_scenario()

# Team stat columns used to derive needs (higher raw = worse for team when inverted)
TEAM_NEED_MAP = {
    "shooting": ("three_point_pct", "three_point_rate", False),  # low 3P% / low 3PA share
    "free_throw": ("free_throw_pct", None, False),
    "ball_security": ("turnover_rate", None, True),  # high TOV = high need
    "offensive_rebounding": ("offensive_rebound_rate", None, False),
    "defensive_rebounding": ("defensive_rebound_rate", None, False),
    "foul_discipline": ("foul_rate", None, True),
    "playmaking": ("assist_rate", None, False),
    "defensive_activity": ("steal_rate", "block_rate", False),
    "rim_pressure": ("efg_pct", "free_throw_rate", False),
}

# Player stat columns for opportunity (low value = high opportunity when invert)
PLAYER_OPP_MAP = {
    "shooting": ("three_point_pct", "efg_pct"),
    "free_throw": ("free_throw_pct",),
    "ball_security": ("turnover_rate",),
    "offensive_rebounding": ("offensive_rebound_rate",),
    "defensive_rebounding": ("defensive_rebound_rate",),
    "foul_discipline": ("foul_rate",),
    "playmaking": ("assist_rate",),
    "defensive_activity": ("steal_rate", "block_rate"),
    "rim_pressure": ("ts_pct", "efg_pct"),
}

HIGHER_IS_WORSE_OPP = {"ball_security", "foul_discipline"}

# Top Priority eligibility — meaningful player gap, team hole, positive projection, position fit
MIN_ACTIONABLE_OPPORTUNITY = 20.0
MIN_OPPORTUNITY_LOW_POSITION_FIT = 40.0
LOW_POSITION_FIT_THRESHOLD = 0.80
MIN_TEAM_NEED_FOR_TOP = 40.0
MIN_POSITION_FIT_MULTIPLIER = 0.65

# Position fit: G = guards, F = wings, C = bigs (Adjusted DPS = raw DPS × multiplier)
POSITION_FIT_MULTIPLIER: dict[str, dict[str, float]] = {
    "G": {
        "shooting": 1.00,
        "free_throw": 1.00,
        "ball_security": 1.00,
        "playmaking": 1.00,
        "offensive_rebounding": 0.65,
        "defensive_rebounding": 0.75,
        "foul_discipline": 0.80,
        "defensive_activity": 0.90,
        "rim_pressure": 0.90,
    },
    "F": {
        "shooting": 1.00,
        "free_throw": 1.00,
        "ball_security": 0.90,
        "playmaking": 0.85,
        "offensive_rebounding": 0.85,
        "defensive_rebounding": 0.90,
        "foul_discipline": 0.90,
        "defensive_activity": 1.00,
        "rim_pressure": 0.95,
    },
    "C": {
        "shooting": 0.90,
        "free_throw": 1.00,
        "ball_security": 0.75,
        "playmaking": 0.65,
        "offensive_rebounding": 1.00,
        "defensive_rebounding": 1.00,
        "foul_discipline": 1.00,
        "defensive_activity": 0.95,
        "rim_pressure": 1.00,
    },
}


def _position_group(position: str) -> str:
    p = str(position or "F").strip().upper()[:1]
    return p if p in ("G", "F", "C") else "F"


def position_fit_multiplier(skill: str, position: str) -> float:
    group = _position_group(position)
    return POSITION_FIT_MULTIPLIER.get(group, POSITION_FIT_MULTIPLIER["F"]).get(skill, 1.0)


def is_actionable_skill(
    opportunity: float,
    projected_points: float,
    team_need: float,
    position_fit: float,
) -> bool:
    min_opp = (
        MIN_OPPORTUNITY_LOW_POSITION_FIT
        if position_fit < LOW_POSITION_FIT_THRESHOLD
        else MIN_ACTIONABLE_OPPORTUNITY
    )
    return (
        opportunity >= min_opp
        and projected_points > 0
        and team_need >= MIN_TEAM_NEED_FOR_TOP
        and position_fit >= MIN_POSITION_FIT_MULTIPLIER
    )


def shooting_actionable_for_player(
    player: pd.Series,
    opportunity: float,
    projected_points: float,
    team_need: float,
    position_fit: float,
    center_median_tpar: float,
) -> bool:
    """
    Three-point actionability with center volume guardrails.
    Rim-only (<=5 season 3PA): projected value treated as 0 for actionability.
    Low-volume (3PA < 30 and rate below center median): never actionable.
    Stretch-eligible centers use the standard actionable filter.
    """
    from models.shot_profile import center_shooting_volume_flags

    flags = center_shooting_volume_flags(player, center_median_tpar)
    if not flags["is_center"]:
        return is_actionable_skill(
            opportunity, projected_points, team_need, position_fit
        )
    if flags["rim_only"] or flags["low_volume"]:
        return False
    return is_actionable_skill(
        opportunity, projected_points, team_need, position_fit
    )


def shooting_projected_for_actionability(
    player: pd.Series,
    projected_points: float,
    center_median_tpar: float,
) -> float:
    """Rim-only centers use 0 projected value when testing actionability only."""
    from models.shot_profile import center_shooting_volume_flags

    flags = center_shooting_volume_flags(player, center_median_tpar)
    if flags["is_center"] and flags["rim_only"]:
        return 0.0
    return projected_points


MIN_FALLBACK_OPPORTUNITY = 10.0


def rank_player_priorities(player_pri: pd.DataFrame) -> pd.DataFrame:
    """
    Order skills for Top / 2nd / 3rd priority.
    Prefer actionable skills (gap + projection + team need + position fit) by adjusted DPS.
    Fallback: opportunity >= 10 by DPS; if none, highest opportunity (> 0) as limited-gap focus.
    Skills with opportunity <= 0 are never ranked as top priorities.
    """
    if player_pri.empty:
        return player_pri
    pri = player_pri.copy()
    if "actionable" not in pri.columns:
        pri["actionable"] = pri.apply(
            lambda r: is_actionable_skill(
                float(r["player_improvement_opportunity"]),
                float(r["projected_points_added"]),
                float(r["team_need_alignment"]),
                float(r.get("position_fit_multiplier", 1.0)),
            ),
            axis=1,
        )
    pri = pri[pri["player_improvement_opportunity"].astype(float) > 0]
    if pri.empty:
        return pri

    actionable = pri[pri["actionable"] == 1].sort_values(
        "development_priority_score", ascending=False
    )
    if not actionable.empty:
        return actionable

    solid_gap = pri[
        pri["player_improvement_opportunity"].astype(float) >= MIN_FALLBACK_OPPORTUNITY
    ].sort_values("development_priority_score", ascending=False)
    if not solid_gap.empty:
        return solid_gap

    return pri.sort_values("player_improvement_opportunity", ascending=False)


def top_priority_skills(player_pri: pd.DataFrame, n: int = 3) -> list[str]:
    ranked = rank_player_priorities(player_pri)
    if ranked.empty:
        return []
    return ranked["skill_category"].head(n).tolist()


def _title_name(name: str) -> str:
    """Proper-case player names (fixes .capitalize() mangling last names)."""
    suffixes = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"}
    parts = []
    for word in str(name).split():
        low = word.lower().rstrip(".")
        if low in suffixes:
            parts.append(word.upper() if low in {"ii", "iii", "iv", "v"} else word.title())
        else:
            parts.append(word.title())
    return " ".join(parts)


def _pick_variant(options: list[str], key: str) -> str:
    return options[hash(key) % len(options)]


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _pool_rank_worst(rank: int, n: int) -> str:
    """Label for _rank_among_teams (rank 1 = worst in the team pool for that stat)."""
    return f"{_ordinal(rank)}-worst of {n}"


def _pool_rank_best(rank: int, n: int) -> str:
    """Best-oriented label when rank 1 = worst (e.g. rank 17 worst → (n-16)th-best of n)."""
    best = max(1, n - rank + 1)
    return f"{_ordinal(best)}-best of {n}"


def _pct(rate: float) -> str:
    return f"{rate * 100:.1f}%"


def normalize_series(s: pd.Series, invert: bool = False) -> pd.Series:
    """Normalize to 0-100 scale using min-max across series."""
    if s.empty or s.nunique() <= 1:
        return pd.Series(50.0, index=s.index)
    mn, mx = s.min(), s.max()
    if mx == mn:
        out = pd.Series(50.0, index=s.index)
    else:
        out = (s - mn) / (mx - mn) * 100
    if invert:
        out = 100 - out
    return out.clip(0, 100)


class ScoringEngine:
    """Compute all DevelopmentIQ scores from teams and players DataFrames."""

    def __init__(self, teams: pd.DataFrame, players: pd.DataFrame):
        self.teams = teams.copy()
        self.players = players.copy()
        self.field_avg: dict[str, float] = {}
        from models.player_advanced import pool_advanced_metrics_ready
        from models.shot_profile import center_position_median_three_point_attempt_rate

        self._use_advanced_metrics = pool_advanced_metrics_ready(self.players)
        self._center_median_tpar = center_position_median_three_point_attempt_rate(
            self.players
        )

    def run_all(self) -> dict[str, pd.DataFrame]:
        self._compute_field_averages()
        team_needs = self.compute_team_needs()
        player_opps = self.compute_player_opportunities()
        priorities = self.compute_development_priorities(team_needs, player_opps)
        leverage = self.compute_development_leverage(team_needs, priorities)
        return {
            "team_need_scores": team_needs,
            "player_opportunity_scores": player_opps,
            "development_priority_scores": priorities,
            "development_leverage_scores": leverage,
        }

    def _compute_field_averages(self) -> None:
        for col in [
            "efg_pct", "three_point_pct", "free_throw_pct", "turnover_rate",
            "offensive_rebound_rate", "defensive_rebound_rate", "steal_rate",
            "block_rate", "foul_rate", "assist_rate", "ts_pct", "usage_rate",
            "three_point_attempt_rate", "free_throw_rate", "assist_turnover_ratio",
            "two_point_pct", "fouls_per_40", "steal_pct", "block_pct",
            "bpm", "obpm", "dbpm", "per", "win_shares_per_40",
            "rim_fg_pct", "rim_attempt_rate", "midrange_fg_pct", "midrange_attempt_rate",
            "corner_three_attempt_rate", "above_break_three_attempt_rate",
        ]:
            if col in self.players.columns:
                series = self.players[col].dropna()
                if len(series):
                    self.field_avg[col] = float(series.mean())

    def compute_team_needs(self) -> pd.DataFrame:
        rows = []
        for _, team in self.teams.iterrows():
            tid = team["team_id"]
            scores = {}
            for skill in SKILL_CATEGORIES:
                need = self._team_need_for_skill(team, skill)
                scores[skill] = need
            row = {"team_id": tid, **{f"{s}_need": scores[s] for s in SKILL_CATEGORIES}}
            rows.append(row)
        df = pd.DataFrame(rows)
        # Re-normalize each need column across teams for interpretability
        for skill in SKILL_CATEGORIES:
            col = f"{skill}_need"
            raw = df[col]
            df[col] = normalize_series(raw, invert=False)

        explanations: list[str] = []
        for _, team in self.teams.iterrows():
            tid = team["team_id"]
            need_row = df.loc[df["team_id"] == tid].iloc[0]
            exp = {
                skill: self._explain_team_need(
                    team, skill, float(need_row[f"{skill}_need"])
                )
                for skill in SKILL_CATEGORIES
            }
            explanations.append(json.dumps(exp))
        df["need_explanations"] = explanations
        return df

    def _league_avg(self, col: str) -> float:
        if col not in self.teams.columns:
            return 0.0
        return float(self.teams[col].mean())

    def _rank_among_teams(self, col: str, value: float, lower_is_worse: bool) -> tuple[int, int]:
        """Return (rank 1=worst for this stat, pool size)."""
        s = self.teams[col].dropna()
        n = len(s)
        if n == 0:
            return 1, 1
        if lower_is_worse:
            rank = int((s < value).sum()) + 1
        else:
            rank = int((s > value).sum()) + 1
        return rank, n

    def _explain_team_need(self, team: pd.Series, skill: str, need: float) -> str:
        """Data-backed team need line for coaches / interviews (not generic copy)."""
        name = str(team.get("team_name", "This team"))
        tid = str(team.get("team_id", ""))
        need_r = round(need)

        if skill == "offensive_rebounding":
            val = float(team.get("offensive_rebound_rate", 0.28) or 0.28)
            avg = self._league_avg("offensive_rebound_rate")
            rank, n = self._rank_among_teams("offensive_rebound_rate", val, lower_is_worse=True)
            if need >= 55:
                return (
                    f"{name} offensive rebounding is {_pct(val)} ({_pool_rank_worst(rank, n)} in our pool; "
                    f"avg {_pct(avg)}) — limited second-chance points push need to {need_r}."
                )
            return (
                f"{name} ORB rate {_pct(val)} is near the {_pct(avg)} pool average "
                f"({_pool_rank_best(rank, n)}), so glass on offense is a lower priority ({need_r})."
            )

        if skill == "defensive_rebounding":
            val = float(team.get("defensive_rebound_rate", 0.28) or 0.28)
            avg = self._league_avg("defensive_rebound_rate")
            rank, n = self._rank_among_teams("defensive_rebound_rate", val, lower_is_worse=True)
            if need >= 55:
                return (
                    f"Defensive glass: {_pct(val)} DRB rate for {name} — {_pool_rank_worst(rank, n)}, "
                    f"vs {_pct(avg)} average — extra opponent possessions drive need {need_r}."
                )
            return (
                f"{name} DRB ({_pct(val)}) is not a glaring hole vs {_pct(avg)} avg "
                f"({_pool_rank_best(rank, n)}); need score {need_r}."
            )

        if skill == "foul_discipline":
            val = float(team.get("foul_rate", 0.20) or 0.20)
            avg = self._league_avg("foul_rate")
            rank, n = self._rank_among_teams("foul_rate", val, lower_is_worse=False)
            if need >= 55:
                return (
                    f"{name} foul rate ({_pct(val)}) is {_pool_rank_worst(rank, n)} teams "
                    f"(pool avg {_pct(avg)}) — rotation and FT damage justify need {need_r}."
                )
            return (
                f"Fouls ({_pct(val)}) are not a top stressor vs {_pct(avg)} average "
                f"({_pool_rank_best(rank, n)}); priority {need_r}."
            )

        if skill == "ball_security":
            val = float(team.get("turnover_rate", 0.17) or 0.17)
            avg = self._league_avg("turnover_rate")
            rank, n = self._rank_among_teams("turnover_rate", val, lower_is_worse=False)
            if need >= 55:
                return (
                    f"{name} turns it over on {_pct(val)} of possessions ({_pool_rank_worst(rank, n)}; "
                    f"avg {_pct(avg)}) — live-ball risk lifts ball-security need to {need_r}."
                )
            return (
                f"Turnover rate {_pct(val)} is manageable vs {_pct(avg)} pool avg "
                f"({_pool_rank_best(rank, n)}); need {need_r}."
            )

        if skill == "shooting":
            tpp = float(team.get("three_point_pct", 0.34) or 0.34)
            tpr = float(team.get("three_point_rate", 0.35) or 0.35)
            efg = float(team.get("efg_pct", 0.50) or 0.50)
            avg_tpp = self._league_avg("three_point_pct")
            avg_tpr = self._league_avg("three_point_rate")
            avg_efg = self._league_avg("efg_pct")
            rank_tpp, n = self._rank_among_teams("three_point_pct", tpp, lower_is_worse=True)
            rank_tpr, _ = self._rank_among_teams("three_point_rate", tpr, lower_is_worse=True)
            if need >= 55:
                return (
                    f"{name} perimeter: {_pct(tpp)} 3P% ({_pool_rank_worst(rank_tpp, n)}, avg {_pct(avg_tpp)}), "
                    f"{_pct(tpr)} of FGA from three ({_pool_rank_worst(rank_tpr, n)} for volume), "
                    f"{_pct(efg)} eFG — spacing need {need_r}."
                )
            return (
                f"Three-point accuracy ({_pct(tpp)}) and volume ({_pct(tpr)} 3PA share) are not the main "
                f"roster weakness (pool 3P% avg {_pct(avg_tpp)}); need {need_r}."
            )

        if skill == "playmaking":
            val = float(team.get("assist_rate", 0.50) or 0.50)
            avg = self._league_avg("assist_rate")
            rank, n = self._rank_among_teams("assist_rate", val, lower_is_worse=True)
            if need >= 55:
                return (
                    f"{name} assist rate {_pct(val)} is {_pool_rank_worst(rank, n)} "
                    f"(avg {_pct(avg)}) — limited creation shows up as need {need_r}."
                )
            return (
                f"Ball movement ({_pct(val)} assist rate) is a relative strength vs {_pct(avg)} "
                f"({_pool_rank_best(rank, n)}), so playmaking need stays low ({need_r})."
            )

        if skill == "defensive_activity":
            st = float(team.get("steal_rate", 0.09) or 0.09)
            bl = float(team.get("block_rate", 0.08) or 0.08)
            drtg = float(team.get("defensive_rating", 100) or 100)
            avg_drtg = self._league_avg("defensive_rating")
            rank_d, n = self._rank_among_teams("defensive_rating", drtg, lower_is_worse=False)
            if need >= 55:
                return (
                    f"{name} defense: {_pct(st)} steal rate, {_pct(bl)} block rate, "
                    f"{drtg:.1f} def rating ({_pool_rank_worst(rank_d, n)}, avg {avg_drtg:.1f}) — "
                    f"event defense need {need_r}."
                )
            return (
                f"Disruption stats and {drtg:.1f} defensive rating are middle-of-pool; "
                f"activity need {need_r}."
            )

        if skill == "free_throw":
            ftp = float(team.get("free_throw_pct", 0.70) or 0.70)
            avg = self._league_avg("free_throw_pct")
            rank, n = self._rank_among_teams("free_throw_pct", ftp, lower_is_worse=True)
            if need >= 55:
                return (
                    f"{name} free-throw shooting: {_pct(ftp)} FT% ({_pool_rank_worst(rank, n)}, "
                    f"avg {_pct(avg)}) — closing games suffer (need {need_r})."
                )
            return (
                f"Free-throw accuracy ({_pct(ftp)}) is not a standout gap vs {_pct(avg)} pool avg "
                f"({_pool_rank_best(rank, n)}); need {need_r}."
            )

        if skill == "rim_pressure":
            ftr = float(team.get("free_throw_rate", 0.32) or 0.32)
            two_p = float(team.get("two_point_pct", 0.48) or 0.48)
            efg = float(team.get("efg_pct", 0.50) or 0.50)
            avg_ftr = self._league_avg("free_throw_rate")
            avg_two = self._league_avg("two_point_pct")
            rank_ftr, n = self._rank_among_teams("free_throw_rate", ftr, lower_is_worse=True)
            rank_two, _ = self._rank_among_teams("two_point_pct", two_p, lower_is_worse=True)
            rim_r = team.get("team_rim_attempt_rate")
            has_rim = rim_r is not None and not (
                isinstance(rim_r, float) and np.isnan(rim_r)
            )
            if need >= 55:
                if has_rim:
                    rim_fg = float(team.get("team_rim_fg_pct", 0.50) or 0.50)
                    return (
                        f"{name} rim pressure: {_pct(float(rim_r))} rim attempt rate, {_pct(rim_fg)} rim FG%, "
                        f"{_pct(ftr)} FTR ({_pool_rank_worst(rank_ftr, n)}) — rim pressure need {need_r}."
                    )
                return (
                    f"{name} paint proxy fallback: {_pct(ftr)} FTR ({_pool_rank_worst(rank_ftr, n)}, avg {_pct(avg_ftr)}), "
                    f"{_pct(two_p)} 2P% ({_pool_rank_worst(rank_two, n)}, avg {_pct(avg_two)}), "
                    f"{_pct(efg)} eFG — rim pressure need {need_r}."
                )
            if has_rim:
                rim_fg = float(team.get("team_rim_fg_pct", 0.50) or 0.50)
                return (
                    f"Rim pressure is not the top team hole "
                    f"({_pct(float(rim_r))} rim attempt rate, {_pct(rim_fg)} rim FG%, FTR {_pct(ftr)}); "
                    f"need {need_r}."
                )
            return (
                f"Paint scoring and line pressure are not the top team hole "
                f"(2P% {_pct(two_p)}, FTR {_pct(ftr)}); need {need_r}."
            )

        return _pick_variant(
            [f"{name} need score {need_r} from normalized 2025-26 team efficiency inputs."],
            f"{tid}:{skill}",
        )

    def _team_need_for_skill(self, team: pd.Series, skill: str) -> float:
        mapping = TEAM_NEED_MAP[skill]
        vals = []
        if skill == "shooting":
            tpp_short = 1 - (team.get("three_point_pct", 0.34) or 0.34)
            efg_short = 1 - (team.get("efg_pct", 0.50) or 0.50)
            tpr_short = 1 - (team.get("three_point_rate", 0.35) or 0.35)
            vals = [tpp_short * 100, efg_short * 60, tpr_short * 60]
            from models.shot_profile import team_shooting_need_boost

            boost = team_shooting_need_boost(team)
            if boost:
                vals.append(50 + boost)
        elif skill == "ball_security":
            vals = [(team.get("turnover_rate", 0.18) or 0.18) * 400]
        elif skill == "foul_discipline":
            vals = [(team.get("foul_rate", 0.20) or 0.20) * 350]
        elif skill == "defensive_rebounding":
            dr = team.get("defensive_rebound_rate", 0.28) or 0.28
            vals = [(1 - dr) * 120]
        elif skill == "offensive_rebounding":
            or_ = team.get("offensive_rebound_rate", 0.28) or 0.28
            vals = [(1 - or_) * 120]
        elif skill == "playmaking":
            ar = team.get("assist_rate", 0.50) or 0.50
            vals = [(1 - ar) * 100]
        elif skill == "defensive_activity":
            st = float(team.get("steal_rate", 0.09) or 0.09)
            bl = float(team.get("block_rate", 0.08) or 0.08)
            drtg = float(team.get("defensive_rating", 100) or 100)
            vals = [
                max(0.0, 1 - st / 0.12) * 50,
                max(0.0, 1 - bl / 0.12) * 50,
                max(0.0, (drtg - 95) / 15) * 50,
            ]
        elif skill == "free_throw":
            ftp = float(team.get("free_throw_pct", 0.70) or 0.70)
            vals = [(1 - ftp) * 100]
        elif skill == "rim_pressure":
            ftr = float(team.get("free_throw_rate", 0.32) or 0.32)
            rim_r = team.get("team_rim_attempt_rate")
            has_rim = rim_r is not None and not (
                isinstance(rim_r, float) and np.isnan(rim_r)
            )
            if has_rim:
                rim_fg = float(team.get("team_rim_fg_pct", 0.50) or 0.50)
                vals = [
                    (1 - float(rim_r)) * 80,
                    (1 - rim_fg) * 70,
                    (1 - ftr) * 60,
                ]
            else:
                two_p = float(team.get("two_point_pct", 0.48) or 0.48)
                efg = float(team.get("efg_pct", 0.50) or 0.50)
                vals = [(1 - ftr) * 80, (1 - two_p) * 70, (1 - efg) * 40]
        return float(np.mean(vals)) if vals else 50.0

    def compute_player_opportunities(self) -> pd.DataFrame:
        rows = []
        qualified = self.players[self.players["mpg"] >= 10].copy()

        for skill in SKILL_CATEGORIES:
            cols = PLAYER_OPP_MAP[skill]
            invert = skill in HIGHER_IS_WORSE_OPP

        for _, player in qualified.iterrows():
            pid = player["player_id"]
            pos = player.get("position", "G")
            pos_peers = qualified[qualified["position"] == pos]
            team_peers = qualified[qualified["team_id"] == player["team_id"]]

            scores = {}
            for skill in SKILL_CATEGORIES:
                scores[skill] = self._player_opp_for_skill(
                    player, skill, pos_peers, team_peers, qualified
                )
            row = {"player_id": pid, **{f"{s}_opportunity": scores[s] for s in SKILL_CATEGORIES}}
            rows.append(row)

        df = pd.DataFrame(rows)
        for skill in SKILL_CATEGORIES:
            col = f"{skill}_opportunity"
            df[col] = normalize_series(df[col], invert=False)
        return df

    def _player_opp_for_skill(
        self,
        player: pd.Series,
        skill: str,
        pos_peers: pd.DataFrame,
        team_peers: pd.DataFrame,
        field: pd.DataFrame,
    ) -> float:
        from models.player_advanced import (
            gaps_for_column,
            opportunity_score,
            position_group,
            scale_gaps,
            stat_or_none,
        )

        pos = position_group(str(player.get("position", "F")))
        mpg = float(player.get("mpg", 15) or 15)
        usage = float(player.get("usage_rate", 0.2) or 0.2)

        if skill == "shooting":
            from models.shot_profile import shooting_opportunity_with_profile

            return shooting_opportunity_with_profile(
                player, pos_peers, field, self.field_avg, scale_gaps=scale_gaps
            )

        if skill == "free_throw":
            from models.shot_profile import free_throw_opportunity_with_profile

            return free_throw_opportunity_with_profile(
                player, pos_peers, field, self.field_avg, scale_gaps=scale_gaps
            )

        if skill == "ball_security":
            from models.player_advanced import ball_security_opportunity_raw

            return ball_security_opportunity_raw(
                player, pos_peers, field, self.field_avg
            )

        if skill == "defensive_rebounding":
            gaps = gaps_for_column(
                player, pos_peers, field, "defensive_rebound_rate", self.field_avg
            )
            if self._use_advanced_metrics:
                dbpm = stat_or_none(player, "dbpm")
                if dbpm is not None and "dbpm" in pos_peers.columns:
                    med = float(pos_peers["dbpm"].dropna().median()) if pos_peers["dbpm"].notna().any() else 0
                    if dbpm < med:
                        gaps.append(min(25.0, (med - dbpm) * 8))
            if mpg < 14:
                gaps = scale_gaps(gaps, 0.85)
            return opportunity_score(
                gaps, core_columns=["defensive_rebound_rate"], player=player
            )

        if skill == "offensive_rebounding":
            gaps = gaps_for_column(
                player, pos_peers, field, "offensive_rebound_rate", self.field_avg
            )
            if pos == "G":
                gaps = scale_gaps(gaps, 0.45)
            elif pos == "F":
                gaps = scale_gaps(gaps, 0.75)
            return opportunity_score(
                gaps, core_columns=["offensive_rebound_rate"], player=player
            )

        if skill == "foul_discipline":
            gaps = gaps_for_column(player, pos_peers, field, "foul_rate", self.field_avg, invert=True)
            fp40 = stat_or_none(player, "fouls_per_40")
            if fp40 is not None and "fouls_per_40" in pos_peers.columns:
                med = float(pos_peers["fouls_per_40"].median())
                if fp40 > med:
                    gaps.append(min(100.0, (fp40 - med) / max(med, 0.1) * 45))
            if mpg >= 24:
                gaps = scale_gaps(gaps, min(1.12, 1.0 + mpg / 80))
            elif mpg < 12:
                gaps = scale_gaps(gaps, 0.7)
            return opportunity_score(gaps, core_columns=["foul_rate"], player=player)

        if skill == "playmaking":
            gaps = gaps_for_column(player, pos_peers, field, "assist_rate", self.field_avg)
            ast_to = stat_or_none(player, "assist_turnover_ratio")
            if ast_to is not None and "assist_turnover_ratio" in pos_peers.columns:
                med = float(pos_peers["assist_turnover_ratio"].median())
                if ast_to < med:
                    gaps.append(min(100.0, (med - ast_to) / max(med, 0.1) * 40))
            if pos == "G":
                if ast_to is not None and "assist_turnover_ratio" in pos_peers.columns:
                    med = float(pos_peers["assist_turnover_ratio"].median())
                    if ast_to < med:
                        gaps = scale_gaps(gaps, 1.1)
            elif pos == "C":
                gaps = scale_gaps(gaps, 0.55)
            if usage < 0.16:
                gaps = scale_gaps(gaps, 0.75)
            return opportunity_score(gaps, core_columns=["assist_rate"], player=player)

        if skill == "defensive_activity":
            stl_gaps = gaps_for_column(player, pos_peers, field, "steal_rate", self.field_avg)
            blk_gaps = gaps_for_column(player, pos_peers, field, "block_rate", self.field_avg)
            if stat_or_none(player, "steal_pct") is not None:
                stl_gaps.extend(
                    gaps_for_column(player, pos_peers, field, "steal_pct", self.field_avg)
                )
            if stat_or_none(player, "block_pct") is not None:
                blk_gaps.extend(
                    gaps_for_column(player, pos_peers, field, "block_pct", self.field_avg)
                )
            if pos == "G":
                stl_w, blk_w = 0.7, 0.3
            elif pos == "C":
                stl_w, blk_w = 0.3, 0.7
            else:
                stl_w, blk_w = 0.5, 0.5
            gaps = []
            if stl_gaps:
                gaps.append(np.mean(stl_gaps) * stl_w)
            if blk_gaps:
                gaps.append(np.mean(blk_gaps) * blk_w)
            if self._use_advanced_metrics:
                dbpm = stat_or_none(player, "dbpm")
                if dbpm is not None and "dbpm" in pos_peers.columns:
                    med = float(pos_peers["dbpm"].dropna().median()) if pos_peers["dbpm"].notna().any() else 0
                    if dbpm < med:
                        gaps.append(min(20.0, (med - dbpm) * 6))
                p_drtg = stat_or_none(player, "player_drtg")
                if p_drtg is not None and "player_drtg" in field.columns:
                    med_dr = float(field["player_drtg"].dropna().median())
                    if p_drtg > med_dr:
                        gaps.append(min(20.0, (p_drtg - med_dr) / 5))
            return opportunity_score(
                [float(x) for x in gaps],
                core_columns=["steal_rate", "block_rate"],
                player=player,
            )

        if skill == "rim_pressure":
            from models.shot_profile import rim_pressure_opportunity_with_profile

            return rim_pressure_opportunity_with_profile(
                player, pos_peers, field, self.field_avg
            )

        invert = skill in HIGHER_IS_WORSE_OPP
        cols = PLAYER_OPP_MAP[skill]
        gaps = []
        for col in cols:
            gaps.extend(
                gaps_for_column(player, pos_peers, field, col, self.field_avg, invert=invert)
            )
        return opportunity_score(gaps, core_columns=list(cols), player=player)

    def compute_development_priorities(
        self,
        team_needs: pd.DataFrame,
        player_opps: pd.DataFrame,
    ) -> pd.DataFrame:
        rows = []
        needs_by_team = team_needs.set_index("team_id")
        opps_by_player = player_opps.set_index("player_id")

        mpg_max = self.players["mpg"].max() or 35

        for _, player in self.players.iterrows():
            if player["mpg"] < 10:
                continue
            pid = player["player_id"]
            tid = player["team_id"]
            if tid not in needs_by_team.index or pid not in opps_by_player.index:
                continue

            team_need = needs_by_team.loc[tid]
            player_opp = opps_by_player.loc[pid]
            role_leverage = min(100, (player["mpg"] / mpg_max) * 100)

            position = str(player.get("position", "F"))

            for skill in SKILL_CATEGORIES:
                opp = float(player_opp[f"{skill}_opportunity"])
                need = float(team_need[f"{skill}_need"])
                realism = REALISM_DEFAULTS[skill]
                impact = IMPACT_DEFAULTS[skill]
                fit = position_fit_multiplier(skill, position)

                raw_dps = (
                    0.30 * opp
                    + 0.30 * need
                    + 0.20 * role_leverage
                    + 0.10 * realism
                    + 0.10 * impact
                )
                dps = raw_dps * fit

                projected = self._projected_impact(player, skill, self.teams, tid)
                if skill == "shooting":
                    projected_action = shooting_projected_for_actionability(
                        player, projected, self._center_median_tpar
                    )
                    actionable = shooting_actionable_for_player(
                        player,
                        opp,
                        projected_action,
                        need,
                        fit,
                        self._center_median_tpar,
                    )
                else:
                    actionable = is_actionable_skill(opp, projected, need, fit)
                explanation = self._build_explanation(
                    player, skill, opp, need, role_leverage, projected, actionable
                )

                rows.append({
                    "player_id": pid,
                    "team_id": tid,
                    "skill_category": skill,
                    "development_priority_score": round(dps, 2),
                    "raw_priority_score": round(raw_dps, 2),
                    "position_fit_multiplier": round(fit, 2),
                    "player_improvement_opportunity": round(opp, 2),
                    "team_need_alignment": round(need, 2),
                    "role_leverage": round(role_leverage, 2),
                    "improvement_realism": realism,
                    "basketball_impact_value": impact,
                    "projected_points_added": round(projected, 2),
                    "actionable": int(actionable),
                    "explanation": explanation,
                })

        return pd.DataFrame(rows)

    def _projected_impact(
        self, player: pd.Series, skill: str, teams: pd.DataFrame, team_id: str
    ) -> float:
        from models.projection_impact import projected_impact_for_skill

        team = teams[teams["team_id"] == team_id]
        team_row = team.iloc[0] if not team.empty else None
        return projected_impact_for_skill(player, skill, team=team_row, scale=1.0)

    def _team_need_clause(self, need: float, area: str, player_id: str) -> str:
        if need >= 60:
            opts = [
                f"The roster profile flags {area} as a clear team gap.",
                f"Staff priority aligns here — {area} shows up as a top team need.",
                f"Lineup fit suffers without more {area} from rotation players.",
            ]
        elif need >= 40:
            opts = [
                f"{area.title()} is a meaningful but not urgent team need.",
                f"The team could use incremental gains in {area}.",
                f"Moderate roster need in {area} supports focusing here.",
            ]
        else:
            opts = [
                f"Team need in {area} is modest; this ranks high mainly on his individual profile.",
                f"Roster need for {area} is lower, so the case is player-driven.",
                f"Less of a team-wide hole in {area}, but still his best actionable skill.",
            ]
        return _pick_variant(opts, f"{player_id}:{area}")

    def _role_clause(self, role: float, mpg: float, player_id: str) -> str | None:
        if role < 55:
            return None
        if mpg >= 28:
            return _pick_variant(
                [
                    f"At {mpg:.1f} MPG he touches enough possessions for gains to matter.",
                    f"Heavy minutes ({mpg:.1f}) amplify any improvement in this area.",
                ],
                f"role_hi:{player_id}",
            )
        if mpg >= 18:
            return _pick_variant(
                [
                    f"Rotation role ({mpg:.1f} MPG) gives a realistic window to apply this work.",
                    f"With {mpg:.1f} minutes per game, practice emphasis can show up in games.",
                ],
                f"role_mid:{player_id}",
            )
        return None

    def _projected_clause(self, projected: float, unit: str, player_id: str) -> str | None:
        if projected <= 0:
            return None
        return _pick_variant(
            [
                f"Rough seasonal value if targeted: ~{projected:.1f} {unit}.",
                f"Modeled improvement scenario: ~{projected:.1f} {unit}.",
            ],
            f"proj:{player_id}",
        )

    def _build_explanation(
        self,
        player: pd.Series,
        skill: str,
        opp: float,
        need: float,
        role: float,
        projected: float,
        actionable: bool,
    ) -> str:
        builders = {
            "shooting": self._explain_shooting,
            "free_throw": self._explain_free_throw,
            "ball_security": self._explain_ball_security,
            "defensive_rebounding": self._explain_def_reb,
            "offensive_rebounding": self._explain_off_reb,
            "foul_discipline": self._explain_fouls,
            "playmaking": self._explain_playmaking,
            "defensive_activity": self._explain_def_activity,
            "rim_pressure": self._explain_rim,
        }
        builder = builders.get(skill, self._explain_fallback)
        return builder(player, opp, need, role, projected, actionable)

    def _explain_shooting(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        from models.shot_profile import (
            CENTER_LOW_VOLUME_SHOOTING_EXPLANATION,
            append_shot_notes,
            center_shooting_volume_flags,
            player_three_point_attempt_rate,
        )

        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        tp = (player.get("three_point_pct") or 0) * 100
        tpa = int(player.get("three_point_attempts") or 0)
        tpar = player_three_point_attempt_rate(player) * 100
        vol = center_shooting_volume_flags(player, self._center_median_tpar)
        if tpa < 30 or tpar < 18:
            lead = (
                f"Three-point shooting is downweighted because {name} does not take enough threes "
                f"({tpa} attempts, {tpar:.0f}% 3PA rate) to treat this as a major spacing role."
            )
        elif tp < 34:
            lead = (
                f"Three-point shooting is flagged because {name} trails peers in 3P% ({tp:.1f}%) "
                f"on meaningful perimeter volume ({tpa} attempts, {tpar:.0f}% 3PA rate)."
            )
        elif actionable:
            lead = f"Even at {tp:.1f}% from deep on {tpa} attempts, incremental gains add spacing value."
        else:
            lead = f"Already a {tp:.1f}% outside shooter; other skills offer more upside."
        parts = [lead]
        if vol["is_center"] and (vol["rim_only"] or vol["low_volume"]) and not actionable:
            parts.append(CENTER_LOW_VOLUME_SHOOTING_EXPLANATION)
        parts.append(self._team_need_clause(need, "perimeter shooting", pid))
        if rc := self._role_clause(role, float(player.get("mpg") or 0), pid):
            parts.append(rc)
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        if not actionable and projected <= 0:
            parts.append("Not recommended as a primary focus.")
        append_shot_notes(parts, player, profile_note=False)
        return " ".join(parts)

    def _explain_free_throw(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        from models.player_advanced import stat_or_none
        from models.shot_profile import append_shot_notes

        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        ft = (player.get("free_throw_pct") or 0) * 100
        fta = int(player.get("free_throw_attempts") or 0)
        ftr = (stat_or_none(player, "free_throw_rate") or 0) * 100
        rim_r = (stat_or_none(player, "rim_attempt_rate") or 0) * 100
        if ft < 65 and (ftr >= 28 or rim_r >= 30):
            lead = (
                f"{name} shoots {ft:.1f}% FT despite getting to the line "
                f"({ftr:.0f}% FTr, {rim_r:.0f}% rim attempt rate) — closing games cost real points."
            )
        elif ft < 65:
            lead = f"{name} is at {ft:.1f}% from the line ({fta} FTA) with limited foul volume."
        elif ft < 72:
            lead = f"Free throws ({ft:.1f}% on {fta} attempts) leave points on the table in a high-touch role."
        elif actionable:
            lead = f"At {ft:.1f}% FT, small mechanical gains still move win probability in tight games."
        else:
            lead = f"Reliable from the stripe ({ft:.1f}%); other categories are sharper development targets."
        parts = [lead, self._team_need_clause(need, "free-throw scoring", pid)]
        if rc := self._role_clause(role, float(player.get("mpg") or 0), pid):
            parts.append(rc)
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        append_shot_notes(parts, player, profile_note=False)
        return " ".join(parts)

    def _explain_ball_security(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        from models.player_advanced import stat_or_none
        from models.shot_profile import append_shot_notes

        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        tov = (player.get("turnover_rate") or 0) * 100
        usage = (player.get("usage_rate") or 0) * 100
        rim_r = stat_or_none(player, "rim_attempt_rate")
        if tov >= 18 and rim_r is not None and rim_r >= 0.32:
            lead = (
                f"Turnover rate ({tov:.1f}%) is high with heavy paint pressure "
                f"({rim_r * 100:.0f}% rim attempts) — live-ball risk may track attacking the rim."
            )
        elif tov >= 18:
            lead = f"Turnover rate ({tov:.1f}%) is high for {usage:.0f}% usage — possessions die in his hands."
        elif tov >= 14 and rim_r is not None and rim_r < 0.22:
            lead = (
                f"{name} turns it over ({tov:.1f}% TO) without high rim pressure — "
                f"ball security may reflect decision-making and creation more than finishing contact."
            )
        elif tov >= 14:
            lead = f"{name} gives up too many live-ball mistakes ({tov:.1f}% TO rate) relative to his touches."
        elif actionable:
            lead = f"Ball security is acceptable ({tov:.1f}% TO) but trimmable with decision-speed work."
        else:
            lead = f"Already steady with the ball ({tov:.1f}% TO rate); focus elsewhere on his profile."
        parts = [lead, self._team_need_clause(need, "ball security", pid)]
        if rc := self._role_clause(role, float(player.get("mpg") or 0), pid):
            parts.append(rc)
        if pc := self._projected_clause(projected, "pts saved", pid):
            parts.append(pc)
        append_shot_notes(parts, player, profile_note=False)
        return " ".join(parts)

    def _explain_def_reb(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        dr = (player.get("defensive_rebound_rate") or 0) * 100
        pos = player.get("position", "F")
        if dr < 10:
            lead = f"Defensive glass rate ({dr:.1f}%) is thin for a {pos} — opponent second chances follow."
        elif dr < 14:
            lead = f"{name} can improve defensive rebounding ({dr:.1f}% DRB rate) to close possessions."
        elif actionable:
            lead = f"Solid DRB profile ({dr:.1f}%) with room to become a go-to glass cleaner."
        else:
            lead = f"Already contributes on the defensive glass ({dr:.1f}%); other skills rank higher."
        parts = [lead, self._team_need_clause(need, "defensive rebounding", pid)]
        if rc := self._role_clause(role, float(player.get("mpg") or 0), pid):
            parts.append(rc)
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        return " ".join(parts)

    def _explain_off_reb(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        oreb = (player.get("offensive_rebound_rate") or 0) * 100
        if oreb < 6:
            lead = f"Offensive rebounding ({oreb:.1f}% ORB) rarely creates extra possessions for this team."
        elif oreb < 10:
            lead = f"{name} can add hidden points by attacking the offensive glass ({oreb:.1f}% ORB rate)."
        elif actionable:
            lead = f"Active on the offensive glass ({oreb:.1f}%) with more available as a motor skill."
        else:
            lead = f"Strong offensive rebounding ({oreb:.1f}%); not the lever that moves his game most."
        parts = [lead, self._team_need_clause(need, "offensive rebounding", pid)]
        if rc := self._role_clause(role, float(player.get("mpg") or 0), pid):
            parts.append(rc)
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        return " ".join(parts)

    def _explain_fouls(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        foul = (player.get("foul_rate") or 0) * 100
        mpg = float(player.get("mpg") or 0)
        if foul >= 5:
            lead = f"Foul rate ({foul:.2f} per minute proxy) limits late-game availability at {mpg:.1f} MPG."
        elif foul >= 3.5:
            lead = f"{name} picks up fouls too often — discipline work keeps him on the floor."
        elif actionable:
            lead = f"Foul discipline is manageable but worth tightening to protect minutes."
        else:
            lead = f"Stays out of foul trouble relative to peers; other priorities stand out."
        parts = [lead, self._team_need_clause(need, "foul discipline", pid)]
        if pc := self._projected_clause(projected, "pts preserved", pid):
            parts.append(pc)
        return " ".join(parts)

    def _explain_playmaking(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        ast = (player.get("assist_rate") or 0) * 100
        if ast < 8:
            lead = f"Assist rate ({ast:.1f}%) shows limited creation — the offense stalls when others are neutralized."
        elif ast < 14:
            lead = f"{name} can grow as a connector ({ast:.1f}% assist rate) with read-and-react reps."
        elif actionable:
            lead = f"Already creates ({ast:.1f}% assist rate); higher-value reads are the next step."
        else:
            lead = f"Primary playmaking ({ast:.1f}% assist rate) is a strength — develop elsewhere first."
        parts = [lead, self._team_need_clause(need, "playmaking", pid)]
        if rc := self._role_clause(role, float(player.get("mpg") or 0), pid):
            parts.append(rc)
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        return " ".join(parts)

    def _explain_def_activity(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        st = (player.get("steal_rate") or 0) * 100
        bl = (player.get("block_rate") or 0) * 100
        if st + bl < 3:
            lead = f"Disruption is low ({st:.1f}% STL, {bl:.1f}% BLK) — defense is mostly positional, not event-creating."
        elif st + bl < 5:
            lead = f"{name} can add event defense: stocks sit at {st:.1f}% steals and {bl:.1f}% blocks."
        elif actionable:
            lead = f"Active hands ({st:.1f}% STL / {bl:.1f}% BLK) with room to become a tone-setter."
        else:
            lead = f"Already impacts with stocks ({st:.1f}% STL, {bl:.1f}% BLK); other gaps matter more."
        parts = [lead, self._team_need_clause(need, "defensive activity", pid)]
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        return " ".join(parts)

    def _explain_rim(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        from models.player_advanced import stat_or_none
        from models.shot_profile import (
            append_shot_notes,
            has_rim_location_data,
            rim_pressure_skill_label,
        )

        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        ts = (player.get("ts_pct") or 0) * 100
        efg = (player.get("efg_pct") or 0) * 100
        rim_fg = stat_or_none(player, "rim_fg_pct")
        rim_r = stat_or_none(player, "rim_attempt_rate")
        tracked = has_rim_location_data(player)
        if tracked and rim_fg is not None and rim_r is not None:
            if rim_r >= 0.35 and rim_fg < 0.52:
                lead = (
                    f"Rim finishing concern: {rim_fg * 100:.1f}% rim FG on {rim_r * 100:.0f}% rim attempt rate "
                    f"(tracked shot profile)."
                )
            elif rim_fg >= 0.58 and rim_r < 0.28:
                lead = (
                    f"{name} finishes efficiently at the rim ({rim_fg * 100:.1f}% rim FG) but "
                    f"low rim frequency ({rim_r * 100:.0f}%) — development is about getting to the paint, not touch."
                )
            elif ts < 54:
                lead = (
                    f"Scoring efficiency gap from tracked rim profile: {rim_fg * 100:.1f}% rim FG, "
                    f"{rim_r * 100:.0f}% rim rate, {ts:.1f}% TS."
                )
            else:
                lead = f"Rim profile is solid ({rim_fg * 100:.1f}% rim FG, {rim_r * 100:.0f}% rim attempts); other skills rank higher."
        elif ts < 50:
            lead = (
                f"Paint pressure proxy: TS% ({ts:.1f}%) and eFG% ({efg:.1f}%) lag — "
                f"public data only (no tracked rim locations)."
            )
        elif ts < 54:
            lead = (
                f"{name} leaves efficiency on the table ({ts:.1f}% TS) — scored from FTr, 2P%, "
                f"and efficiency only when tracked rim data is unavailable."
            )
        elif actionable:
            lead = f"Decent scorer ({ts:.1f}% TS); marginal rim-pressure gains still move offensive rating."
        else:
            lead = f"Efficient scorer ({ts:.1f}% TS); shooting or security may be sharper levers."
        need_phrase = rim_pressure_skill_label(player).lower()
        parts = [lead, self._team_need_clause(need, need_phrase, pid)]
        if rc := self._role_clause(role, float(player.get("mpg") or 0), pid):
            parts.append(rc)
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        append_shot_notes(parts, player)
        return " ".join(parts)

    def _explain_fallback(
        self, player: pd.Series, opp: float, need: float, role: float,
        projected: float, actionable: bool,
    ) -> str:
        name = _title_name(player.get("player_name", "Player"))
        pid = str(player.get("player_id", ""))
        label = "this skill area"
        parts = [f"{name} profiles with development room in {label}."]
        parts.append(self._team_need_clause(need, label, pid))
        if pc := self._projected_clause(projected, "pts", pid):
            parts.append(pc)
        return " ".join(parts)

    def _production_index_by_player(self) -> pd.Series:
        """Production blend 0–100; uses BPM/PER/WS when present, else TS%/usage/PPG."""
        scores: list[float] = []
        for _, row in self.players.iterrows():
            scores.append(self._production_score_for_player(row))
        raw = pd.Series(scores, index=self.players["player_id"])
        return pd.Series(normalize_series(raw, invert=False), index=self.players["player_id"])

    def _norm_col(self, col: str, val: float, invert: bool = False) -> float:
        if col not in self.players.columns:
            return 50.0
        series = self.players[col].dropna()
        if series.empty:
            return 50.0
        lo, hi = float(series.min()), float(series.max())
        if hi <= lo:
            return 50.0
        x = (val - lo) / (hi - lo)
        if invert:
            x = 1 - x
        return max(0.0, min(100.0, x * 100))

    def _production_score_for_player(self, player: pd.Series) -> float:
        if not self._use_advanced_metrics:
            return (
                float(player.get("ts_pct", 0.52) or 0.52) * 100
                + float(player.get("usage_rate", 0.2) or 0.2) * 50
                + float(player.get("ppg", 8) or 8) * 3
            )

        bpm = player.get("bpm")
        if bpm is not None and not (isinstance(bpm, float) and np.isnan(bpm)):
            parts = [
                (self._norm_col("bpm", float(bpm)), 0.30),
                (self._norm_col("ts_pct", float(player.get("ts_pct", 0.52) or 0.52)), 0.20),
                (
                    self._norm_col(
                        "usage_rate", float(player.get("usage_rate", 0.2) or 0.2)
                    ),
                    0.15,
                ),
                (self._norm_col("ppg", float(player.get("ppg", 8) or 8)), 0.15),
            ]
            per = player.get("per")
            if per is not None and not (isinstance(per, float) and np.isnan(per)):
                parts.append((self._norm_col("per", float(per)), 0.10))
            ws40 = player.get("win_shares_per_40")
            if ws40 is None or (isinstance(ws40, float) and np.isnan(ws40)):
                ws40 = player.get("win_shares")
            if ws40 is not None and not (isinstance(ws40, float) and np.isnan(ws40)):
                col = (
                    "win_shares_per_40"
                    if "win_shares_per_40" in self.players.columns
                    and player.get("win_shares_per_40") is not None
                    else "win_shares"
                )
                parts.append((self._norm_col(col, float(ws40)), 0.10))
            total = sum(w for _, w in parts)
            return sum(s * w for s, w in parts) / total

        return (
            float(player.get("ts_pct", 0.52) or 0.52) * 100
            + float(player.get("usage_rate", 0.2) or 0.2) * 50
            + float(player.get("ppg", 8) or 8) * 3
        )  # rare: pool flagged advanced but row missing BPM

    def compute_development_leverage(
        self,
        team_needs: pd.DataFrame,
        priorities: pd.DataFrame,
    ) -> pd.DataFrame:
        production_by_player = self._production_index_by_player()
        rows = []
        for pid in priorities["player_id"].unique():
            player_pri = priorities[priorities["player_id"] == pid]
            player = self.players[self.players["player_id"] == pid]
            if player.empty:
                continue
            player = player.iloc[0]
            tid = player["team_id"]

            ranked = rank_player_priorities(player_pri)
            skills = top_priority_skills(player_pri, 3)
            top_priority = skills[0] if len(skills) > 0 else ""
            second = skills[1] if len(skills) > 1 else ""
            third = skills[2] if len(skills) > 2 else ""

            production = float(production_by_player.get(pid, 50.0))

            upside = float(ranked["development_priority_score"].head(3).mean())
            team_row = team_needs[team_needs["team_id"] == tid]
            if not team_row.empty:
                need_cols = [f"{s}_need" for s in SKILL_CATEGORIES]
                team_need_vec = team_row.iloc[0][need_cols].astype(float)
                top_skills = ranked["skill_category"].head(3).tolist()
                alignment = float(
                    np.mean([team_need_vec.get(f"{s}_need", 50) for s in top_skills])
                )
            else:
                alignment = 50.0

            mpg = player.get("mpg", 15) or 15
            role_lev = min(100, mpg / 35 * 100)

            class_year = str(player.get("class_year_2026_27", "Unknown"))
            runway_map = {"Fr": 85, "So": 80, "Jr": 70, "Sr": 55, "Gr": 50, "Unknown": 60}
            runway = runway_map.get(class_year, 60)

            dls = (
                0.30 * production
                + 0.30 * upside
                + 0.20 * alignment
                + 0.10 * role_lev
                + 0.10 * runway
            )

            rows.append({
                "player_id": pid,
                "team_id": tid,
                "development_leverage_score": round(dls, 2),
                "top_priority": top_priority,
                "second_priority": second,
                "third_priority": third,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["development_leverage_score"] = normalize_series(
                df["development_leverage_score"], invert=False
            )
        return df
