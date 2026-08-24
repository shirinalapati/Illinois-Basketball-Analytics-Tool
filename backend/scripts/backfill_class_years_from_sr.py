"""
Backfill player class_year on SR caches from Sports Reference roster Class column.

Older caches often defaulted to Jr / Unknown because Class values like JR/SO were
not normalized. This script re-fetches each team page (or uses --team) and updates
only class_year / class_year_source on cached players.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(BACKEND_ROOT))

from ingest_sports_reference import (  # noqa: E402
    REQUEST_DELAY,
    TEAM_SLUGS,
    TEAMS_SPEC,
    _cache_path,
    _load_cache,
    _lookup_class,
    _save_cache,
    class_from_roster,
    fetch_html,
)
from models.class_year import advance_class_year, normalize_class_year  # noqa: E402


def backfill_team(tid: str, tname: str, delay: float) -> tuple[int, int]:
    slug = TEAM_SLUGS.get(tid)
    cached = _load_cache(tid)
    if not slug or not cached or not cached.get("players"):
        return 0, 0

    html = fetch_html(slug)
    cmap = class_from_roster(html)
    updated = 0
    known = 0
    for player in cached["players"]:
        name = player.get("player_name", "")
        cls = _lookup_class(cmap, name)
        if cls:
            known += 1
            if normalize_class_year(player.get("class_year")) != cls:
                updated += 1
            player["class_year"] = cls
            player["class_year_source"] = "sports_reference_roster"
        else:
            # Keep existing non-unknown labels; do not invent.
            if normalize_class_year(player.get("class_year")) == "Unknown":
                player["class_year"] = "Unknown"
                player["class_year_source"] = "unknown"
    _save_cache(tid, cached)
    time.sleep(delay)
    print(f"  ✓ {tname}: {known}/{len(cached['players'])} class labels, {updated} changed")
    return known, updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", action="append", default=[], help="team_id to backfill (repeatable)")
    parser.add_argument(
        "--teams-file",
        type=str,
        default="",
        help="Text file with one team_id per line",
    )
    parser.add_argument("--delay", type=float, default=5.0)
    parser.add_argument(
        "--only-unknown",
        action="store_true",
        help="Only teams that currently have any Unknown class_year in cache",
    )
    args = parser.parse_args()

    file_teams: list[str] = []
    if args.teams_file:
        file_teams = [
            line.strip()
            for line in Path(args.teams_file).read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    wanted = set(args.team) | set(file_teams)
    targets = []
    for tid, tname, _ in TEAMS_SPEC:
        if wanted and tid not in wanted:
            continue
        if args.only_unknown:
            cached = _load_cache(tid)
            if not cached:
                continue
            if not any(
                normalize_class_year(p.get("class_year")) == "Unknown"
                for p in cached.get("players", [])
            ):
                continue
        targets.append((tid, tname))

    print(f"Backfilling class years for {len(targets)} teams (delay={args.delay}s)...")
    total_known = total_updated = 0
    for tid, tname in targets:
        try:
            known, updated = backfill_team(tid, tname, args.delay)
            total_known += known
            total_updated += updated
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {tname}: {exc}")
            time.sleep(args.delay * 2)
    print(f"Done. labels={total_known}, changed={total_updated}")


if __name__ == "__main__":
    main()
