"""2026-27 portal transfers into the DevelopmentIQ team universe."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TRANSFER_MARKER = "2026-27 transfer"


def is_transfer_in_2027(data_source: str | None) -> bool:
    """True when the player was moved onto this team for 2026-27 per roster pipeline."""
    if not data_source:
        return False
    return TRANSFER_MARKER in str(data_source).lower()


def transfer_from_school(data_source: str | None) -> str | None:
    """Parse prior school from data_source, e.g. '… transfer from Boise State'."""
    if not data_source:
        return None
    m = re.search(r"2026-27 transfer from\s+(.+?)(?:\s*·|$)", str(data_source), re.I)
    return m.group(1).strip() if m else None


@lru_cache(maxsize=1)
def transfer_in_keys_from_json() -> frozenset[tuple[str, str]]:
    """(normalized_name, to_team_id) pairs from roster_transfers_2027.json."""
    path = DATA_DIR / "roster_transfers_2027.json"
    if not path.exists():
        return frozenset()
    payload = json.loads(path.read_text())
    keys: set[tuple[str, str]] = set()
    for row in payload.get("transfers", []):
        name = _norm_name(str(row.get("player_name", "")))
        to_tid = str(row.get("to_team_id", "")).strip()
        if name and to_tid:
            keys.add((name, to_tid))
    return frozenset(keys)


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def is_transfer_player(
    *,
    data_source: str | None = None,
    player_name: str | None = None,
    team_id: str | None = None,
) -> bool:
    if is_transfer_in_2027(data_source):
        return True
    if player_name and team_id:
        return (_norm_name(player_name), team_id) in transfer_in_keys_from_json()
    return False
