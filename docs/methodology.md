# DevelopmentIQ — Technical Methodology

## Problem Statement

College basketball staffs must decide which player-skill improvements create the most **team value** during a season. Development cannot be evaluated in isolation: priority depends on player weakness, team need, role/minutes, realism of improvement, and basketball value of the skill.

## Data Layer

| Source (intended) | Metrics |
|-------------------|---------|
| BartTorvik | Team/player efficiency, rates |
| Sports Reference | Box score, shooting splits, advanced stats |
| NCAA public stats | Games, minutes |
| **v1 (2025-26)** | 103 teams (Big Ten/SEC/Big 12/ACC/Big East + 24 mid-majors), Sports Reference ingestion |

**Rotation filter:** MPG ≥ 10 OR total minutes ≥ 250.

## Database Schema (SQLite, PostgreSQL-compatible)

- `teams` — team efficiency profile
- `players` — rotation player rates
- `team_need_scores` — 9 need dimensions per team
- `player_opportunity_scores` — 9 opportunity dimensions per player
- `development_priority_scores` — player × skill DPS rows
- `development_leverage_scores` — composite leverage per player

## Team Need Alignment

Derived from team rates vs field expectations. Examples:

- **Shooting need:** low `three_point_pct`, low `three_point_rate`, low `efg_pct`
- **Ball security:** high `turnover_rate`
- **Defensive rebounding:** low `defensive_rebound_rate`
- **Foul discipline:** high `foul_rate`
- **Playmaking:** low `assist_rate`
- **Defensive activity:** low steal/block rates, weaker `defensive_rating`
- **Rim pressure / finishing:** low aggregated `team_rim_attempt_rate`, low aggregated `team_rim_fg_pct`, low `free_throw_rate`

Scores normalized 0–100 across the curated team universe.

## Player Improvement Opportunity

Gap vs positional peers and field median. Higher-is-worse stats (turnovers, fouls) invert the gap logic. Shooting development is only heavily weighted if the player actually shoots a meaningful number of threes.

## Development Priority Score (DPS)

```
DPS = 0.30 × Opportunity
    + 0.30 × Team Need
    + 0.20 × Role Leverage (MPG normalized)
    + 0.10 × Improvement Realism (category defaults)
    + 0.10 × Basketball Impact Value (category defaults)
```

### Improvement Realism & Basketball Impact (fixed priors)

These numbers are **fixed scores (0–100) per skill**, not calculated from player stats in the database. They reflect common coaching judgment about (1) how realistic a one-year jump is and (2) how much that skill usually helps winning. Each counts for only **10%** of DPS; player opportunity, team need, and role still drive almost all of the ranking.

**Realism** — calibrated from year-over-year player movement (2024–25 → 2025–26):

| Skill | Score | Median \|Δ\| in matched sample (n=235 returners) |
|-------|------:|--------------------------------------------------|
| Free throws | 100 | FT% (largest typical swing) |
| Three-point shooting | 90 | 3P%, eFG% |
| Rim pressure | 80 | TS%, eFG% |
| Playmaking | 70 | Assist rate, AST/G |
| Ball security | 60 | TOV rate, TOV/G |
| Defensive rebounding | 50 | DRB/G |
| Foul discipline | 40 | PF/G |
| Offensive rebounding | 30 | ORB/G |
| Defensive activity | 20 | STL/G, BLK/G (smallest typical swing) |

Computed in `backend/scripts/calibrate_realism_priors.py` from `sr_cache_prior` + `sr_cache`.

**Impact** — derived from Dean Oliver’s **Four Factors** (offensive efficiency decomposition):

| Skill | Score | Four-factor mapping |
|-------|------:|---------------------|
| Ball security | 100 | Turnover rate (25%) |
| Three-point shooting | 95 | Effective FG% — spacing share (24 pts of 40%) |
| Rim pressure | 93 | Effective FG% + free-throw rate (rim finishing / getting to line) |
| Offensive rebounding | 77 | Offensive rebound rate (20%) |
| Defensive rebounding | 50 | Secondary — ends defensive possessions |
| Playmaking | 36 | Secondary — creation (partial eFG enabler) |
| Defensive activity | 31 | Secondary — disruption |
| Foul discipline | 22 | Secondary — availability / fouls |
| Free throws | 20 | Free-throw rate — converting (7.5 pts of 15%); lower than rim pressure because factors weight attempts at the line |

Computed in `backend/scripts/calibrate_impact_priors.py` (raw weights → normalized 20–100).

### Top Priority (player development focus)

A skill is **actionable** when `opportunity ≥ 15` and `projected_points_added > 0`.

**Top Priority** = highest DPS among actionable skills for that player. If none are actionable, use the skill with the highest improvement opportunity (relative best focus).

### Skill Categories

1. Three-Point Shooting  
2. Free Throw Shooting  
3. Ball Security  
4. Defensive Rebounding  
5. Offensive Rebounding  
6. Foul Discipline  
7. Playmaking  
8. Defensive Activity  
9. Rim Pressure / Finishing

Team rim splits are aggregated from tracked player shot profiles:

```
team_rim_attempt_rate = sum(player rim attempts) / sum(player FGA)
team_rim_fg_pct       = sum(player rim makes) / sum(player rim attempts)
```

## Projected Impact (YoY-calibrated scenarios)

Same 235 same-school returners (2024–25 → 2025–26). Increments = 75th percentile of **positive** YoY gains, clipped; ceilings = p90 of current-season stats. See `projection_calibration.json` and `calibrate_projection_scenario.py`.

| Skill | Formula (season proxy) |
|-------|------------------------|
| 3P Shooting | `3PA × (target_3p - current_3p) × 3`, +5% increment, ~41% ceiling |
| FT Shooting | `FTA × (target_ft - current_ft)`, +8% increment, ~86% ceiling |
| Turnovers | `prevented_TO × team_PPP` (~12% reduction) |
| Fouls | `fouls_reduced × 0.7` (~12% reduction) |
| DRB / ORB | `games × (+0.04 / +0.02 DRB/ORB per game) × proxy` |
| Playmaking | `games × +0.04 AST/G × 1.5` |
| Rim | `FGA proxy × (target_TS - current) × 0.8`, +4.5% TS, ~64% ceiling |

## Development Leverage Score

```
DLS = 0.30 × Production
    + 0.30 × Upside (top-3 DPS avg)
    + 0.20 × Need match (team need on top-3 skills)
    + 0.10 × Minutes (MPG / 35 × 100)
    + 0.10 × Class runway (Fr 85, So 80, Jr 70, Sr 55, Gr 50, Unknown 60)
```

**Production index:** uses the full-pool advanced blend when coverage is complete:
`30% BPM + 20% TS% + 15% usage + 15% PPG + 10% PER + 10% WS/40`, then min-max normalized to 0–100 across all rotation players in the database. If a future dataset lacks complete advanced coverage, the model falls back uniformly to `Raw = TS%×100 + usage×50 + PPG×3`.

**Class runway caveat:** Uses projected 2026-27 class labels when available. Because eligibility and roster statuses can change, unknown or uncertain players are labeled Unknown rather than guessed.

## API Endpoints

- `GET /api/overview` — dashboard aggregates  
- `GET /api/teams`, `/api/teams/{id}`  
- `GET /api/teams/{id}/development-board`  
- `GET /api/players/{id}`  
- `GET /api/leaderboard/leverage`  
- `POST /api/simulate` — slider-driven impact  

## Stack

Python 3 · pandas · FastAPI · SQLite · React · TypeScript · Vite · Tailwind · Recharts
