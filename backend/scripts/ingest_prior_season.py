#!/usr/bin/env python3
"""
Fetch 2024-25 player stats into backend/data/sr_cache_prior/ for YoY realism calibration.
Uses the same 103-team universe as the main ingest.

Example:
  python ingest_prior_season.py --delay 8
  python ingest_prior_season.py --missing-only --delay 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from ingest_sports_reference import (  # noqa: E402
    DATA_DIR,
    REQUEST_DELAY,
    STATS_LABEL,
    configure_ingest,
    ingest_all,
    ingest_team,
)
from team_slugs import TEAM_SLUGS  # noqa: E402
from teams_universe import TEAMS_SPEC  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest 2024-25 Sports Reference cache")
    parser.add_argument("--missing-only", action="store_true")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch all teams (needed after adding per-game stat fields)",
    )
    parser.add_argument("--delay", type=float, default=8.0)
    args = parser.parse_args()

    import ingest_sports_reference as ing

    configure_ingest(
        sr_year=2025,
        cache_dir=DATA_DIR / "sr_cache_prior",
        stats_label="2024-25",
    )
    ing.REQUEST_DELAY = args.delay
    print(f"Ingesting {STATS_LABEL} → {ing.CACHE_DIR} (delay={args.delay}s)...")
    if args.refresh:
        for tid, tname, conf in TEAMS_SPEC:
            slug = TEAM_SLUGS.get(tid)
            if not slug:
                continue
            try:
                _, pl = ingest_team(tid, tname, conf, slug, force_refresh=True)
                print(f"  ✓ {tname}: {len(pl)} players")
            except Exception as e:
                print(f"  ✗ {tname}: {e}")
        print("Refresh complete.")
    else:
        teams, players = ingest_all(only_missing=args.missing_only)
        print(f"Done: {len(teams)} teams, {len(players)} rotation players")


if __name__ == "__main__":
    main()
