import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { Team, TeamNeeds } from '../types';
import { SKILL_LABELS, SKILL_ORDER } from '../types';
import { useTeamQuery } from '../lib/useTeamQuery';
import { TEAM_PROFILE_STATS, buildTeamStatRanks } from '../lib/teamStatRank';
import TeamSelect from '../components/TeamSelect';
import NeedsRadar from '../charts/NeedsRadar';
import { TeamNeedsBarChart } from '../charts/AppCharts';
import ApiError from '../components/ApiError';

export default function TeamNeedsMap() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useTeamQuery();
  const [team, setTeam] = useState<Team | null>(null);
  const [needs, setNeeds] = useState<TeamNeeds | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.teams().then(setTeams).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!teamId) return;
    setError('');
    api
      .team(teamId)
      .then((r) => {
        setTeam(r.team);
        setNeeds(r.needs as TeamNeeds);
      })
      .catch((e) => setError(e.message));
  }, [teamId]);

  const ranked = needs
    ? SKILL_ORDER.map((key) => ({
        key,
        score: Number(needs[`${key}_need` as keyof TeamNeeds] ?? 0),
        label: SKILL_LABELS[key] || key,
      })).sort((a, b) => b.score - a.score)
    : [];

  const statRanks = useMemo(
    () => (team && teams.length ? buildTeamStatRanks(teams, team.team_id) : {}),
    [teams, team]
  );

  const orbPct = team ? team.offensive_rebound_rate * 100 : 0;
  const orbRaw = team ? (1 - team.offensive_rebound_rate) * 120 : 0;
  const orbNeed = needs ? Number(needs.offensive_rebounding_need) : 0;
  const topNeed = ranked[0];
  const lowNeed = ranked.length ? ranked[ranked.length - 1] : null;

  const needExplainLead = (key: string) => {
    const full = needs?.need_explanations?.[key];
    if (!full) return '';
    const dash = full.indexOf(' — ');
    return dash > 0 ? full.slice(0, dash) : full;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl font-bold">Team Needs Map</h2>
          <p className="text-gray-400 text-sm mt-1 max-w-2xl">
            Ranked from 2025-26 team efficiency stats (Sports Reference). Each line cites this
            team&apos;s numbers vs the {teams.length || 103}-team pool — not generic copy.{' '}
            <Link
              to="/methodology#team-needs-map-skillset"
              className="text-illini-orange hover:underline"
            >
              View methodology
            </Link>{' '}
            to see how team need scores are calculated for all nine skills (raw weakness formula per
            skill, then min–max scaling across the {teams.length || 103}-team pool).
          </p>
          {team && needs && topNeed && lowNeed ? (
            <p className="text-gray-500 text-xs mt-2 max-w-2xl leading-relaxed">
              <strong className="text-gray-400">Example ({team.team_name}):</strong>{' '}
              <strong className="text-gray-300">{topNeed.label}</strong> (
              <span className="text-illini-orange tabular-nums">{Math.round(topNeed.score)}</span>
              ){needExplainLead(topNeed.key) ? ` — ${needExplainLead(topNeed.key)}` : ''}. Lowest:{' '}
              <strong className="text-gray-300">{lowNeed.label}</strong> (
              <span className="tabular-nums">{Math.round(lowNeed.score)}</span>
              ){needExplainLead(lowNeed.key) ? ` — ${needExplainLead(lowNeed.key)}` : ''}.
            </p>
          ) : null}
        </div>
        <TeamSelect teams={teams} value={teamId} onChange={setTeamId} />
      </div>

      {error && <ApiError message={error} />}

      {team && !error && (
        <>
          <div className="grid md:grid-cols-3 gap-4">
            <div className="card md:col-span-1">
              <h3 className="font-display text-lg text-illini-orange">{team.team_name}</h3>
              <p className="text-sm text-gray-400">{team.conference} · 2025-26</p>
              <p className="text-xs text-gray-500 mt-3">
                Rank vs {teams.length || 103}-team pool (#1 = best for that stat). ORtg / DRtg / Pace
                are team-specific (from SR season totals when ingested, otherwise estimated from
                four-factor rates).
              </p>
              <dl className="mt-2 space-y-2 text-sm">
                {TEAM_PROFILE_STATS.map((stat) => {
                  const r = statRanks[stat.key];
                  return (
                    <div key={stat.key} className="flex justify-between gap-2">
                      <dt className="text-gray-500">{stat.label}</dt>
                      <dd className="text-right tabular-nums">
                        {stat.format(team)}
                        {r?.rank ? (
                          <span className="text-gray-500 text-xs ml-1.5">
                            #{r.rank}/{r.poolSize}
                          </span>
                        ) : null}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            </div>
            <div className="card md:col-span-2">
              <h3 className="text-sm text-gray-400 mb-2">Team Needs Radar</h3>
              {needs && <NeedsRadar needs={needs as unknown as Record<string, number>} />}
            </div>
          </div>

          <div className="card space-y-4">
            <h3 className="font-display text-lg font-semibold text-illini-orange">
              How the 0–100 need score is calculated
            </h3>
            <p className="text-sm text-gray-300 leading-relaxed">
              <Link
                to="/methodology#team-needs-map-skillset"
                className="text-illini-orange font-medium hover:underline"
              >
                View methodology → Team Needs Map Skillset
              </Link>{' '}
              for the full raw-weakness formula for each of the nine skills (shooting, rebounding, ball
              security, rim pressure, etc.). Below is the same two-step process with an offensive-rebounding
              example for the team selected above.
            </p>
            <p className="text-sm text-gray-400 leading-relaxed">
              The number on each row
              {topNeed ? (
                <>
                  {' '}
                  (e.g. <strong className="text-white">{topNeed.label}</strong> ={' '}
                  <strong className="text-illini-orange tabular-nums">{Math.round(topNeed.score)}</strong>)
                </>
              ) : null}{' '}
              is not the raw stat (ORB%, assist rate, etc.). It is a{' '}
              <strong className="text-white">0–100 rank vs {teams.length || 103} teams</strong> after two steps.
            </p>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div className="rounded-lg border border-surface-border bg-surface/50 p-3 space-y-2">
                <p className="text-xs uppercase tracking-wide text-gray-500">Step 1 — Raw weakness</p>
                <p className="font-mono text-xs text-illini-orange">Raw = (1 − ORB%) × 120</p>
                <p className="text-gray-500 text-xs">
                  (Other skills use different team stats: turnovers, assist rate, foul rate, etc.)
                </p>
                {team && (
                  <p className="text-gray-300 text-xs leading-relaxed">
                    <strong className="text-white">{team.team_name}:</strong> ORB{' '}
                    {orbPct.toFixed(1)}% → Raw = (1 − {team.offensive_rebound_rate.toFixed(4)}) × 120 ={' '}
                    <strong className="text-illini-orange">{orbRaw.toFixed(2)}</strong>
                  </p>
                )}
              </div>
              <div className="rounded-lg border border-surface-border bg-surface/50 p-3 space-y-2">
                <p className="text-xs uppercase tracking-wide text-gray-500">Step 2 — Scale to 0–100</p>
                <p className="font-mono text-xs text-illini-orange leading-relaxed">
                  Need = (Raw − min Raw) / (max Raw − min Raw) × 100
                </p>
                <p className="text-gray-500 text-xs">
                  Min/max Raw come from the worst and best teams in the {teams.length || 103}-team pool for that skill.
                </p>
                {team && needs && (
                  <p className="text-gray-300 text-xs leading-relaxed">
                    <strong className="text-white">{team.team_name} offensive rebounding need:</strong>{' '}
                    <strong className="text-illini-orange">{Math.round(orbNeed)}</strong>
                    <span className="text-gray-500">
                      {' '}
                      (ORB {orbPct.toFixed(1)}% — scaled vs the {teams.length || 103}-team pool; not the same as the top overall
                      need above)
                    </span>
                  </p>
                )}
              </div>
            </div>
            <p className="text-xs text-gray-500">
              <strong className="text-gray-400">0</strong> = relative strength in the pool ·{' '}
              <strong className="text-gray-400">100</strong> = biggest weakness in the pool
            </p>
          </div>

          <div className="card">
            <h3 className="font-display text-lg font-semibold mb-2">Ranked Team Needs</h3>
            <p className="text-sm text-gray-500 mb-4">
              0 = relative strength · 100 = biggest weakness in the {teams.length || 103}-team pool. Explanations use pool rank:{' '}
              <strong className="text-gray-400">17th-worst of {teams.length || 103}</strong> = only 16 teams are worse on that stat;{' '}
              <strong className="text-gray-400">
                {teams.length ? `${teams.length - 16}th` : '87th'}-best of {teams.length || 103}
              </strong>{' '}
              = relative strength.
            </p>
            <TeamNeedsBarChart items={ranked} />
            <div className="space-y-4 mt-6 border-t border-surface-border pt-6">
              {ranked.map((n, i) => (
                <div key={n.key} className="border-l-4 border-illini-orange pl-4 py-2">
                  <h4 className="font-semibold text-white">
                    {i + 1}. {n.label} — <span className="text-illini-orange">{Math.round(n.score)}</span>
                  </h4>
                  <p className="text-sm text-gray-400 mt-1 leading-relaxed">
                    {needs?.need_explanations?.[n.key] ||
                      'Need score from normalized team efficiency inputs (2025-26).'}
                  </p>
                  <div className="mt-2 h-2 bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full bg-illini-orange rounded-full"
                      style={{ width: `${Math.min(100, n.score)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
