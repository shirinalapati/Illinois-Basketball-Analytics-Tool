import type { Team } from '../types';

export type TeamStatRankConfig = {
  key: string;
  label: string;
  format: (t: Team) => string;
  /** #1 = best in the team pool for this stat */
  higherIsBetter: boolean;
  getValue: (t: Team) => number;
};

export const TEAM_PROFILE_STATS: TeamStatRankConfig[] = [
  {
    key: 'offensive_rating',
    label: 'Off Rtg',
    getValue: (t) => t.offensive_rating,
    format: (t) => t.offensive_rating?.toFixed(1) ?? '—',
    higherIsBetter: true,
  },
  {
    key: 'defensive_rating',
    label: 'Def Rtg',
    getValue: (t) => t.defensive_rating,
    format: (t) => t.defensive_rating?.toFixed(1) ?? '—',
    higherIsBetter: false,
  },
  {
    key: 'pace',
    label: 'Pace',
    getValue: (t) => t.pace,
    format: (t) => t.pace?.toFixed(1) ?? '—',
    higherIsBetter: true,
  },
  {
    key: 'efg_pct',
    label: 'eFG%',
    getValue: (t) => t.efg_pct,
    format: (t) => `${(t.efg_pct * 100).toFixed(1)}%`,
    higherIsBetter: true,
  },
  {
    key: 'turnover_rate',
    label: 'TOV Rate',
    getValue: (t) => t.turnover_rate,
    format: (t) => `${(t.turnover_rate * 100).toFixed(1)}%`,
    higherIsBetter: false,
  },
  {
    key: 'defensive_rebound_rate',
    label: 'Def Reb%',
    getValue: (t) => t.defensive_rebound_rate,
    format: (t) => `${(t.defensive_rebound_rate * 100).toFixed(1)}%`,
    higherIsBetter: true,
  },
];

/** Rank 1 = best in pool; ties get the same rank (competition ranking). */
export function rankInPool(
  teams: Team[],
  teamId: string,
  getValue: (t: Team) => number,
  higherIsBetter: boolean
): { rank: number; poolSize: number } {
  const poolSize = teams.length;
  if (!poolSize) return { rank: 0, poolSize: 0 };

  const sorted = [...teams].sort((a, b) => {
    const diff = getValue(b) - getValue(a);
    return higherIsBetter ? diff : -diff;
  });

  let rank = 1;
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && getValue(sorted[i]) !== getValue(sorted[i - 1])) {
      rank = i + 1;
    }
    if (sorted[i].team_id === teamId) {
      return { rank, poolSize };
    }
  }
  return { rank: poolSize, poolSize };
}

export function buildTeamStatRanks(
  teams: Team[],
  teamId: string
): Record<string, { rank: number; poolSize: number }> {
  const out: Record<string, { rank: number; poolSize: number }> = {};
  for (const stat of TEAM_PROFILE_STATS) {
    out[stat.key] = rankInPool(teams, teamId, stat.getValue, stat.higherIsBetter);
  }
  return out;
}
