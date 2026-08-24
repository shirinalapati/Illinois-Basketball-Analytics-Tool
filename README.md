**Demo video:** [Watch the DevelopmentIQ walkthrough](https://drive.google.com/file/d/1BV9dSOzJztT-65cPt1Ihy-GhIcKIT_O8/view?usp=sharing)
# DevelopmentIQ

**College Basketball Player Development Priority Engine**

A full-stack decision-support app that identifies which **player–skill** improvements would create the most value for a team by combining player gaps, team needs, role/minutes, improvement realism, and basketball impact.

![Duke Blue #003087](https://img.shields.io/badge/Duke-Blue-003087) ![React + TypeScript](https://img.shields.io/badge/React-TypeScript-61DAFB) ![FastAPI](https://img.shields.io/badge/FastAPI-009688)

**Technical formulas:** [`docs/methodology.md`](docs/methodology.md) · In-app **Methodology** page (`/methodology`)

**Live demo:** [college-basketball-player-development-tool.vercel.app](https://college-basketball-player-development-tool.vercel.app)

---

## Problem

College staffs must answer:

> **Which skill improvement would create the most value for this player and this team?**

DevelopmentIQ is not a generic rankings dashboard. It weights every player × skill combination with:

1. **Player improvement opportunity** (gap vs position peers and pool)  
2. **Team need alignment** (roster weakness vs 103-team pool)  
3. **Role leverage** (minutes)  
4. **Improvement realism** and **basketball impact** (calibrated priors)  
5. **Position fit** (adjusted DPS so guards are not steered into big-man skills without a real gap)

**Top Priority** uses an **actionable filter** when possible; otherwise the app shows **relative focus (limited gap)**. **Development Leverage** is a separate **whole-player** score (production, upside, need match, minutes, class runway) — not per skill.

---

## Data (v1)

| Item | Detail |
|------|--------|
| **Stats season** | 2025–26 (Sports Reference) |
| **Roster lens** | Projected **2026–27** teams (transfers / departures applied) |
| **Teams** | **103** (power + selected mid-majors) |
| **Players** | **922** rotation players (≥10 MPG or 250+ minutes) |
| **Skills** | 9 categories (shooting, FT, ball security, ORB/DRB, fouls, playmaking, defensive activity, rim pressure) |

**Sources:** Sports Reference ingest (`ingest_sports_reference.py`), roster/transfer files (`roster_transfers_2027.json`, `roster_status.csv`), shot-profile enrichment, advanced stats (BPM, PER, Win Shares) for production index.

Incoming freshmen without college baselines are excluded from the scored pool.

---

## Quick Start

### One command

```bash
cd developmentiq-cbb
chmod +x start.sh
./start.sh
```

Open **http://localhost:5173** (UI). API: **http://localhost:8000** (`/api/*`, `/docs`).

### Prerequisites

- Python 3.10+  
- Node.js 18+

### First-time setup

```bash
npm run setup    # from project root — venv, pip install, seed DB, npm install
```

### Manual (two terminals)

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed_database.py
uvicorn api.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

### Rebuild data after roster / ingest changes

```bash
cd backend/scripts
python build_full_dataset.py
python seed_database.py
```

Optional: `python ingest_sports_reference.py --missing-only` (rate-limited SR cache refresh).

---

## App Pages

| Route | Purpose |
|-------|---------|
| `/` | Overview — mission, DPS weight chart, default program needs, leverage leaders |
| `/team-needs` | Team Needs Map — ranked weaknesses + radar |
| `/development-board` | Per-team priorities, Proj. Value, Top Priority, leverage |
| `/player/:id` | Profile — stats, ranks, top 3 skills, DPS breakdown |
| `/simulator` | Improvement sliders + projected value |
| `/leaderboard` | Development Leverage across pool (filters) |
| `/methodology` | Plain-language + technical documentation |

Team selection persists in `localStorage` across board, simulator, and needs views.

---

## Model (short)

**Development Priority Score (per skill, per player):**

```
DPS = 0.30×Opportunity + 0.30×TeamNeed + 0.20×Role + 0.10×Realism + 0.10×Impact
Adjusted DPS = raw DPS × position fit
```

**Top Priority:** highest adjusted DPS among **actionable** skills (opportunity, team need, projected value, position-fit gates); fallback to relative focus if none qualify.

**Development Leverage (one score per player):**

```
0.30×Production + 0.30×Upside (avg DPS on top 3 skills) + 0.20×Need match + 0.10×Minutes + 0.10×Class runway
```

**2026–27 rosters:** edit `backend/data/roster_transfers_2027.json` (transfers / departures), then `build_full_dataset.py` + `seed_database.py`. See `build_transfer_list.py` for ESPN-assisted transfer list refresh.

**Validation:** `python -m scripts.run_pre_submit_checks` (from `backend/` with venv active).

---

## Project Structure

```
developmentiq-cbb/
├── frontend/            # React + Vite + Tailwind + Recharts
├── backend/
│   ├── api/             # FastAPI
│   ├── models/          # Scoring, shot profile, projections, simulator
│   ├── scripts/         # Ingest, roster build, seed, checks
│   └── data/            # SQLite, CSVs, roster JSON
└── docs/
    └── methodology.md   # Technical formula reference
```

---

## Why Useful

- **Coaches:** Development plans tied to team needs; actionable vs relative labels; simulator scenarios.  
- **GM / ops:** Team Needs Map; compare severe team need to actionable DPS on roster; leverage leaderboard; portal/recruiting context when no internal pathway exists.  
- **Default team context:** San Jose State (`san_jose_state`) on overview and deep links.

---
