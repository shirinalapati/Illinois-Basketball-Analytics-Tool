"""Projected class-year helpers for 2026-27 roster context."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

CLASS_ORDER = ("Fr", "So", "Jr", "Sr", "Gr", "Unknown")

_ALIASES = {
    "fr": "Fr",
    "f": "Fr",
    "freshman": "Fr",
    "so": "So",
    "sophomore": "So",
    "jr": "Jr",
    "j": "Jr",
    "junior": "Jr",
    "sr": "Sr",
    "senior": "Sr",
    "gr": "Gr",
    "grad": "Gr",
    "graduate": "Gr",
    "unknown": "Unknown",
}

_ADVANCE = {
    "Fr": "So",
    "So": "Jr",
    "Jr": "Sr",
    "Sr": "Gr",
    "Gr": "Gr",
}

PROJECTED_CLASS_PATH = Path(__file__).resolve().parent.parent / "data" / "projected_class_year_2027.csv"


def normalize_class_year(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Unknown"
    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "null", "—", "-"}:
        return "Unknown"

    # Prefer athletics-site phrases ("Redshirt Junior", etc.).
    low = re.sub(r"[^a-z0-9 ]+", " ", raw.lower())
    low = " ".join(low.split())
    for full, short in (
        ("redshirt senior", "Sr"),
        ("rs senior", "Sr"),
        ("graduate student", "Gr"),
        ("grad student", "Gr"),
        ("redshirt junior", "Jr"),
        ("rs junior", "Jr"),
        ("redshirt sophomore", "So"),
        ("rs sophomore", "So"),
        ("redshirt freshman", "Fr"),
        ("rs freshman", "Fr"),
        ("fifth year", "Gr"),
        ("senior", "Sr"),
        ("junior", "Jr"),
        ("sophomore", "So"),
        ("freshman", "Fr"),
        ("graduate", "Gr"),
    ):
        if full in low:
            return short

    compact = raw.replace(".", "").strip().lower()
    if compact in _ALIASES:
        return _ALIASES[compact]
    # Sports Reference roster tables use FR/SO/JR/SR.
    return _ALIASES.get(compact[:2], "Unknown")


def advance_class_year(value: Any) -> str:
    current = normalize_class_year(value)
    return _ADVANCE.get(current, "Unknown")


def add_projected_class_year(players: pd.DataFrame) -> pd.DataFrame:
    """Add/normalize projected 2026-27 class labels without inventing unknown classes."""
    out = players.copy()
    if "class_year_2026_27" in out.columns:
        projected = out["class_year_2026_27"].map(normalize_class_year)
    else:
        projected = pd.Series(["Unknown"] * len(out), index=out.index)

    unknown = projected.eq("Unknown")
    if "class_year" in out.columns:
        projected.loc[unknown] = out.loc[unknown, "class_year"].map(advance_class_year)

    out["class_year_2026_27"] = projected.fillna("Unknown").map(normalize_class_year)

    if PROJECTED_CLASS_PATH.exists():
        overrides = pd.read_csv(PROJECTED_CLASS_PATH).fillna("")
        if {"player_name", "team_id", "class_year_2026_27"}.issubset(overrides.columns):
            override_map = {
                (_norm_name(row["player_name"]), str(row["team_id"]).strip()): normalize_class_year(
                    row["class_year_2026_27"]
                )
                for _, row in overrides.iterrows()
                if normalize_class_year(row["class_year_2026_27"]) != "Unknown"
            }
            if override_map:
                out["class_year_2026_27"] = out.apply(
                    lambda row: override_map.get(
                        (_norm_name(row.get("player_name", "")), str(row.get("team_id", "")).strip()),
                        row["class_year_2026_27"],
                    ),
                    axis=1,
                )
    return out


def _norm_name(name: Any) -> str:
    return " ".join(str(name or "").strip().lower().replace(".", "").split())
