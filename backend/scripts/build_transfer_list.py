"""
Build roster_transfers_2027.json from ESPN top-100 transfer article + supplemental commits.
Only includes moves where destination is one of the app's 103 teams and
the player exists on the source team in our ingested roster.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from teams_universe import TEAMS_SPEC

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_PATH = DATA_DIR / "roster_transfers_2027.json"
ESPN_PATH = DATA_DIR / "espn_top100_transfers.txt"
STAYING_PATH = DATA_DIR / "nba_draft_staying_2026.json"
WITHDRAWALS_PATH = DATA_DIR / "nba_draft_withdrawals_2026.json"

VALID_TEAMS = {t[0] for t in TEAMS_SPEC}

# Display name -> team_id (103-team universe only)
SCHOOL_TO_TEAM: dict[str, str] = {
    "Alabama": "alabama",
    "Arizona": "arizona",
    "Arizona State": "arizona_state",
    "Arkansas": "arkansas",
    "Auburn": "auburn",
    "Baylor": "baylor",
    "Boise State": "boise_state",
    "Boston College": "boston_college",
    "Bradley": "bradley",
    "Butler": "butler",
    "BYU": "byu",
    "California": "california",
    "Cal": "california",
    "Cincinnati": "cincinnati",
    "Clemson": "clemson",
    "Colorado": "colorado",
    "Creighton": "creighton",
    "DePaul": "depaul",
    "Duke": "duke",
    "Florida": "florida",
    "Florida Atlantic": "florida_atlantic",
    "Florida State": "florida_state",
    "Georgia": "georgia",
    "Georgia Tech": "georgia_tech",
    "Georgetown": "georgetown",
    "Gonzaga": "gonzaga",
    "Grand Canyon": "grand_canyon",
    "Houston": "houston",
    "Illinois": "illinois",
    "Indiana": "indiana",
    "Iowa": "iowa",
    "Iowa State": "iowa_state",
    "Kansas": "kansas",
    "Kansas State": "kansas_state",
    "Kentucky": "kentucky",
    "LSU": "lsu",
    "Louisville": "louisville",
    "Marquette": "marquette",
    "Maryland": "maryland",
    "Memphis": "memphis",
    "Miami": "miami",
    "Michigan": "michigan",
    "Michigan State": "michigan_state",
    "Minnesota": "minnesota",
    "Missouri": "missouri",
    "Mississippi State": "mississippi_state",
    "Nebraska": "nebraska",
    "Nevada": "nevada",
    "New Mexico": "new_mexico",
    "North Carolina": "north_carolina",
    "NC State": "nc_state",
    "North Carolina State": "nc_state",
    "Northwestern": "northwestern",
    "Notre Dame": "notre_dame",
    "Ohio State": "ohio_state",
    "Oklahoma": "oklahoma",
    "Oklahoma State": "oklahoma_state",
    "Ole Miss": "ole_miss",
    "Oregon": "oregon",
    "Penn State": "penn_state",
    "Pitt": "pittsburgh",
    "Pittsburgh": "pittsburgh",
    "Providence": "providence",
    "Purdue": "purdue",
    "Rutgers": "rutgers",
    "Saint Mary's": "saint_marys",
    "St. Mary's": "saint_marys",
    "San Diego State": "san_diego_state",
    "San Jose State": "san_jose_state",
    "San José State": "san_jose_state",
    "SJSU": "san_jose_state",
    "Seton Hall": "seton_hall",
    "SMU": "smu",
    "South Carolina": "south_carolina",
    "Stanford": "stanford",
    "St. John's": "st_johns",
    "Syracuse": "syracuse",
    "TCU": "tcu",
    "Tennessee": "tennessee",
    "Texas": "texas",
    "Texas A&M": "texas_am",
    "Texas Tech": "texas_tech",
    "UAB": "uab",
    "UCLA": "ucla",
    "UConn": "uconn",
    "Connecticut": "uconn",
    "UNLV": "unlv",
    "USC": "usc",
    "Utah": "utah",
    "Vanderbilt": "vanderbilt",
    "Villanova": "villanova",
    "Virginia": "virginia",
    "Virginia Tech": "virginia_tech",
    "VCU": "vcu",
    "Wake Forest": "wake_forest",
    "Washington": "washington",
    "West Virginia": "west_virginia",
    "Wisconsin": "wisconsin",
    "Xavier": "xavier",
}

# Overrides / commits not in ESPN top-100 parse
SUPPLEMENTAL = [
    {"player_name": "Vyctorius Miller", "from_team_id": "oklahoma_state", "to_team_id": "georgetown"},
    {"player_name": "Josiah Parker", "from_team_id": "florida_atlantic", "to_team_id": "georgetown"},
    {"player_name": "Elmarko Jackson", "from_team_id": "kansas", "to_team_id": "georgetown"},
    {"player_name": "Jaland Lowe", "from_team_id": "kentucky", "to_team_id": "georgetown"},
    {"player_name": "KJ Lewis", "from_team_id": "georgetown", "to_team_id": "usc"},
    {"player_name": "Eric Reibe", "from_team_id": "uconn", "to_team_id": "usc"},
    {"player_name": "Malik Mack", "from_team_id": "georgetown", "to_team_id": "providence"},
    {"player_name": "P.J. Haggerty", "from_team_id": "kansas_state", "to_team_id": "texas_am"},
    {"player_name": "Kayden Mingo", "from_team_id": "penn_state", "to_team_id": "baylor"},
]

# Stale / incorrect ESPN lines (wrong direction)
BLOCKLIST = {
    ("vyctorius miller", "georgetown", "oklahoma_state"),
}


def _school_to_team(name: str) -> str | None:
    name = name.strip()
    if name in SCHOOL_TO_TEAM:
        tid = SCHOOL_TO_TEAM[name]
        return tid if tid in VALID_TEAMS else None
    return None


def parse_espn_transfers(text: str) -> list[dict]:
    rows: list[dict] = []
    current_name: str | None = None
    for line in text.splitlines():
        m_head = re.match(r"^## \d+\.\s+(.+?),\s", line)
        if m_head:
            current_name = m_head.group(1).strip()
            continue
        m_xfer = re.match(r"^Transferring from (.+)$", line)
        if m_xfer and current_name:
            rest = m_xfer.group(1).strip()
            if " to " in rest:
                from_s, to_s = rest.split(" to ", 1)
            else:
                from_s, to_s = rest, ""
            from_tid = _school_to_team(from_s)
            to_tid = _school_to_team(to_s) if to_s else None
            if from_tid and to_tid:
                rows.append(
                    {
                        "player_name": current_name,
                        "from_team_id": from_tid,
                        "to_team_id": to_tid,
                        "source": "espn_top100",
                    }
                )
    return rows


def load_player_index() -> dict[tuple[str, str], str]:
    """Index players on SR caches (pre-transfer rosters)."""
    roster = load_roster_entries()
    return {(e["norm_name"], e["team_id"]): e["player_id"] for e in roster}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower()).replace(".", "")


def load_roster_entries() -> list[dict]:
    """All cached players with display name and team (2025-26 SR rosters)."""
    from ingest_sports_reference import CACHE_DIR

    entries: list[dict] = []
    for path in CACHE_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        for p in data.get("players", []):
            name = str(p["player_name"]).strip()
            tid = str(p["team_id"])
            entries.append(
                {
                    "player_name": name,
                    "team_id": tid,
                    "norm_name": _norm(name),
                    "player_id": str(p["player_id"]),
                }
            )
    return entries


# Seniors / eligibility exits (not staying in draft, but off 2026-27 rosters)
DEPARTURES_ELIGIBILITY = [
    {"player_name": "Kylan Boswell", "team_id": "illinois"},
    {"player_name": "Tarris Reed Jr.", "team_id": "uconn"},
    {"player_name": "Jaron Pierre Jr.", "team_id": "smu"},
    {"player_name": "B.J. Edwards", "team_id": "smu"},
    {"player_name": "Kevin Miller", "team_id": "smu"},
    {"player_name": "Tre Donaldson", "team_id": "miami"},
]

# Portal with no commit to a 103-team school (removed from last known team)
PORTAL_UNCOMMITTED = [
    {"player_name": "Milan Momcilovic", "team_id": "iowa_state"},
    {"player_name": "Tounde Yessoufou", "team_id": "baylor"},
    {"player_name": "Abdi Bashir Jr.", "team_id": "kansas_state"},
]


def _load_json_player_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("players", [])


def resolve_on_roster(name: str, team_id: str, roster: list[dict]) -> dict | None:
    """Match a display name to a cached roster row on a team."""
    n = _norm(name)
    for e in roster:
        if e["team_id"] == team_id and e["norm_name"] == n:
            return e
    last = n.split()[-1] if n.split() else ""
    cands = [
        e
        for e in roster
        if e["team_id"] == team_id and last and last in e["norm_name"]
    ]
    if len(cands) == 1:
        return cands[0]
    return None


def _add_departure(
    found: dict[tuple[str, str], dict],
    entry: dict,
    reason: str,
) -> None:
    key = (entry["norm_name"], entry["team_id"])
    found[key] = {
        "player_name": entry["player_name"],
        "team_id": entry["team_id"],
        "reason": reason,
    }


def build_departures(
    text: str,
    roster: list[dict],
    transfer_names: set[str],
) -> list[dict]:
    """
    Remove players from 2026-27 rosters when they:
    - Stayed in the 2026 NBA Draft (authoritative list)
    - Exhausted eligibility / left as seniors
    - Entered portal without a commit to a 103-team school
    """
    found: dict[tuple[str, str], dict] = {}
    withdraw_keys: set[tuple[str, str]] = set()
    for w in _load_json_player_list(WITHDRAWALS_PATH):
        entry = resolve_on_roster(w["player_name"], w["team_id"], roster)
        if entry:
            withdraw_keys.add((entry["norm_name"], entry["team_id"]))

    # 1. Confirmed NBA draft stayers (all 103-team programs)
    for s in _load_json_player_list(STAYING_PATH):
        if _norm(s["player_name"]) in transfer_names:
            continue
        entry = resolve_on_roster(s["player_name"], s["team_id"], roster)
        if not entry:
            continue
        key = (entry["norm_name"], entry["team_id"])
        if key in withdraw_keys:
            continue
        _add_departure(found, entry, "nba_draft")

    # 2. Eligibility / replaced seniors
    for spec in DEPARTURES_ELIGIBILITY:
        if _norm(spec["player_name"]) in transfer_names:
            continue
        entry = resolve_on_roster(spec["player_name"], spec["team_id"], roster)
        if entry:
            _add_departure(found, entry, "eligibility")

    # 3. Portal, no destination in our 103-team universe
    for spec in PORTAL_UNCOMMITTED:
        if _norm(spec["player_name"]) in transfer_names:
            continue
        entry = resolve_on_roster(spec["player_name"], spec["team_id"], roster)
        if entry:
            _add_departure(found, entry, "transfer_portal")

    # 4. ESPN prose with explicit departures (avoid fuzzy full-roster scan)
    lower = text.lower()
    prose_rules: list[tuple[str, str, str]] = [
        ("keaton wagler going to the nba", "illinois", "nba_draft"),
        ("kylan boswell out of eligibility", "illinois", "eligibility"),
        ("dailyn swain seemingly set on the nba draft", "texas", "nba_draft"),
        ("christian anderson off to the nba", "texas_tech", "nba_draft"),
        ("tarris reed jr. out of eligibility", "uconn", "eligibility"),
    ]
    for phrase, team_id, reason in prose_rules:
        if phrase not in lower:
            continue
        for entry in roster:
            if entry["team_id"] == team_id and phrase.split()[0] in entry["norm_name"]:
                if _norm(entry["player_name"]) in transfer_names:
                    continue
                _add_departure(found, entry, reason)
                break

    # Flemings: "departing NBA draft lottery pick" in Thomas section
    if "departing nba draft lottery pick" in lower:
        entry = resolve_on_roster("Kingston Flemings", "houston", roster)
        if entry and entry["norm_name"] not in transfer_names:
            _add_departure(found, entry, "nba_draft")

    # SMU eligibility trio (ESPN #91 outlook)
    if "boopie miller, jaron pierre jr. and b.j. edwards all out of eligibility" in lower:
        for name in ("Kevin Miller", "Jaron Pierre Jr.", "B.J. Edwards"):
            entry = resolve_on_roster(name, "smu", roster)
            if entry:
                _add_departure(found, entry, "eligibility")

    return sorted(found.values(), key=lambda d: (d["team_id"], d["player_name"]))


def validate_and_dedupe(candidates: list[dict], player_index: dict) -> tuple[list[dict], list[str]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    logs: list[str] = []

    for c in candidates:
        name = c["player_name"].strip()
        fr = c["from_team_id"]
        to = c["to_team_id"]
        if (_norm(name), fr, to) in BLOCKLIST:
            continue
        if (name.lower(), fr, to) in seen:
            continue
        if fr not in VALID_TEAMS or to not in VALID_TEAMS:
            continue
        if fr == to:
            continue
        if (_norm(name), fr) not in player_index:
            logs.append(f"SKIP (not on roster): {name} @ {fr}")
            continue
        seen.add((name.lower(), fr, to))
        out.append(
            {
                "player_name": name,
                "from_team_id": fr,
                "to_team_id": to,
            }
        )
    return out, logs


def main() -> None:
    candidates: list[dict] = []
    if ESPN_PATH.exists():
        text = ESPN_PATH.read_text(encoding="utf-8", errors="replace")
        candidates.extend(parse_espn_transfers(text))
    else:
        print(f"Warning: ESPN file not found at {ESPN_PATH}")
    candidates.extend(SUPPLEMENTAL)  # supplemental overrides ESPN for same player

    player_index = load_player_index()
    validated, logs = validate_and_dedupe(candidates, player_index)

    by_player: dict[str, dict] = {}
    for row in validated:
        by_player[_norm(row["player_name"])] = row
    final_transfers = sorted(by_player.values(), key=lambda r: (r["to_team_id"], r["player_name"]))
    transfer_names = {_norm(t["player_name"]) for t in final_transfers}

    roster = load_roster_entries()
    departures: list[dict] = []
    if ESPN_PATH.exists():
        text = ESPN_PATH.read_text(encoding="utf-8", errors="replace")
        departures = build_departures(text, roster, transfer_names)

    dep_validated: list[dict] = []
    dep_logs: list[str] = []
    roster_keys = {(e["norm_name"], e["team_id"]) for e in roster}
    for d in departures:
        key = (_norm(d["player_name"]), d["team_id"])
        if key not in roster_keys:
            dep_logs.append(f"SKIP departure (not on roster): {d['player_name']} @ {d['team_id']}")
            continue
        dep_validated.append(d)
    departures = sorted(dep_validated, key=lambda d: (d["team_id"], d["player_name"]))

    payload = {
        "season_label": "2026-27",
        "description": (
            "Transfer portal commits for 2026-27. Only moves to/from teams in the "
            "103-team DevelopmentIQ universe; players must exist on the source team "
            "in our 2025-26 stats baseline. Departures remove NBA draft / eligibility exits."
        ),
        "sources": [
            "ESPN top-100 transfer tracker",
            "supplemental reported commits",
            "nba_draft_staying_2026.json",
            "nba_draft_withdrawals_2026.json",
        ],
        "transfers": final_transfers,
        "departures": departures,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {len(final_transfers)} transfers, {len(departures)} departures to {OUT_PATH}")
    skipped = [l for l in logs if l.startswith("SKIP")]
    if skipped:
        print(f"Skipped {len(skipped)} (player not on source team in DB)")
        for line in skipped[:15]:
            print(f"  {line}")
        if len(skipped) > 15:
            print(f"  ... and {len(skipped) - 15} more")


if __name__ == "__main__":
    main()
