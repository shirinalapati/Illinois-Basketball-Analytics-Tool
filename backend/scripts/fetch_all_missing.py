#!/usr/bin/env python3
"""Fetch all missing SR caches with retries; rebuild DB when complete."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from cache_from_markdown import cache_team
from ingest_sports_reference import _load_cache, fetch_html
from team_slugs import TEAM_SLUGS
from teams_universe import TEAMS_SPEC


def main() -> None:
    missing = [(tid, TEAM_SLUGS[tid]) for tid, _, _ in TEAMS_SPEC if not _load_cache(tid) and tid in TEAM_SLUGS]
    print(f"Fetching {len(missing)} teams...", flush=True)
    ok, fail = 0, []
    for i, (tid, slug) in enumerate(missing, 1):
        for attempt in range(4):
            try:
                html = fetch_html(slug)
                n = cache_team(tid, html)
                print(f"[{i}/{len(missing)}] ✓ {tid}: {n} players", flush=True)
                ok += 1
                time.sleep(8)
                break
            except Exception as e:
                if attempt == 3:
                    print(f"[{i}/{len(missing)}] ✗ {tid}: {e}", flush=True)
                    fail.append(tid)
                time.sleep(20 * (attempt + 1))
    cached = sum(1 for tid, _, _ in TEAMS_SPEC if _load_cache(tid))
    print(f"Done: {cached}/103 cached, failed: {len(fail)}", flush=True)
    if fail:
        print("Failed:", fail, flush=True)
    if cached >= 103:
        subprocess.run([sys.executable, str(SCRIPT_DIR / "build_full_dataset.py")], check=True)
        subprocess.run([sys.executable, str(SCRIPT_DIR / "seed_database.py")], check=True)
        print("Database rebuilt.", flush=True)


if __name__ == "__main__":
    main()
