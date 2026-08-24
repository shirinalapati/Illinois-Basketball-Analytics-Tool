#!/usr/bin/env python3
"""
Ingest Sports Reference data in small batches to avoid 429 rate limits.
Usage: python ingest_batches.py [--batch-size 8] [--delay 22] [--pause 90]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from ingest_sports_reference import CACHE_DIR, REQUEST_DELAY, _load_cache, ingest_team
from team_slugs import TEAM_SLUGS
from teams_universe import TEAMS_SPEC


def flush_print(msg: str) -> None:
    print(msg, flush=True)


def missing_teams() -> list[tuple[str, str, str]]:
    out = []
    for tid, tname, conf in TEAMS_SPEC:
        if not _load_cache(tid):
            out.append((tid, tname, conf))
    return out


def run_batches(batch_size: int, delay: float, pause: float) -> None:
    global REQUEST_DELAY
    import ingest_sports_reference as ing

    ing.REQUEST_DELAY = delay
    REQUEST_DELAY = delay

    pending = missing_teams()
    total = len(TEAMS_SPEC)
    cached = total - len(pending)
    flush_print(f"Starting batch ingest: {cached}/{total} already cached, {len(pending)} to fetch")

    if not pending:
        flush_print("All 103 teams already cached.")
        _finalize()
        return

    batches = [pending[i : i + batch_size] for i in range(0, len(pending), batch_size)]
    failed: list[str] = []

    for bnum, batch in enumerate(batches, 1):
        flush_print(f"\n=== Batch {bnum}/{len(batches)} ({len(batch)} teams) ===")
        for tid, tname, conf in batch:
            slug = TEAM_SLUGS.get(tid)
            if not slug:
                flush_print(f"  ✗ {tname}: no slug")
                failed.append(tid)
                continue
            try:
                _, players = ingest_team(tid, tname, conf, slug)
                flush_print(f"  ✓ {tname}: {len(players)} players")
            except Exception as e:
                flush_print(f"  ✗ {tname}: {e}")
                failed.append(tid)

        cached_now = total - len(missing_teams())
        flush_print(f"Progress: {cached_now}/{total} teams cached")

        if bnum < len(batches):
            flush_print(f"Pausing {pause:.0f}s before next batch...")
            time.sleep(pause)

    remaining = missing_teams()
    flush_print(f"\nDone fetching. Cached: {total - len(remaining)}/{total}")
    if failed:
        flush_print(f"Failed ({len(failed)}): {failed[:20]}...")
    if not remaining:
        _finalize()
    else:
        flush_print("Re-run later to retry missing teams.")


def _finalize() -> None:
    flush_print("\nRebuilding database...")
    subprocess.run([sys.executable, str(SCRIPT_DIR / "build_full_dataset.py")], check=True)
    subprocess.run([sys.executable, str(SCRIPT_DIR / "seed_database.py")], check=True)
    flush_print("✓ All 103 teams built and database seeded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch Sports Reference ingestion")
    parser.add_argument("--batch-size", type=int, default=8, help="Teams per batch")
    parser.add_argument("--delay", type=float, default=22.0, help="Seconds between team requests")
    parser.add_argument("--pause", type=float, default=90.0, help="Seconds between batches")
    args = parser.parse_args()
    run_batches(args.batch_size, args.delay, args.pause)
