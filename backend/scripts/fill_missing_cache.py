#!/usr/bin/env python3
"""Fetch missing teams via urllib (slow) and fill sr_cache. Run when rate limit cooled."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from ingest_sports_reference import CACHE_DIR, _load_cache, fetch_html
from team_slugs import TEAM_SLUGS
from teams_universe import TEAMS_SPEC

# Import after path setup
from cache_from_markdown import cache_team


def main() -> None:
    missing = [(tid, TEAM_SLUGS[tid]) for tid, _, _ in TEAMS_SPEC if not _load_cache(tid) and tid in TEAM_SLUGS]
    print(f"Missing {len(missing)} teams", flush=True)
    for i, (tid, slug) in enumerate(missing, 1):
        url_path = Path(f"/tmp/sr_{tid}.md")
        for attempt in range(5):
            try:
                html = fetch_html(slug)
                url_path.write_text(html)
                n = cache_team(tid, html)
                print(f"[{i}/{len(missing)}] ✓ {tid}: {n} players", flush=True)
                time.sleep(25)
                break
            except Exception as e:
                print(f"[{i}/{len(missing)}] ✗ {tid} attempt {attempt+1}: {e}", flush=True)
                time.sleep(60 * (attempt + 1))
    cached = sum(1 for tid, _, _ in TEAMS_SPEC if _load_cache(tid))
    print(f"Cached {cached}/103", flush=True)
    if cached == 103:
        subprocess.run([sys.executable, str(SCRIPT_DIR / "build_full_dataset.py")], check=True)
        subprocess.run([sys.executable, str(SCRIPT_DIR / "seed_database.py")], check=True)


if __name__ == "__main__":
    main()
