import { useEffect, useState, useMemo, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../lib/api';
import { Team, DevelopmentBoardRow } from '../types';
import { SKILL_LABELS } from '../types';
import { PROJ_VALUE_COLUMN_TOOLTIP } from '../lib/projectionCopy';
import { useTeamQuery } from '../lib/useTeamQuery';
import TeamSelect from '../components/TeamSelect';
import ApiError from '../components/ApiError';
import ChartCard from '../charts/ChartCard';
import { DevBoardDpsChart, DpsWeightDonut } from '../charts/AppCharts';

const PRIORITY_OPTIONS = Object.entries(SKILL_LABELS).map(([k, v]) => ({ id: k, label: v }));
const CLASS_OPTIONS = ['So', 'Jr', 'Sr', 'Gr'];

export default function PlayerDevelopmentBoard() {
  const [searchParams] = useSearchParams();
  const highlightPlayer = searchParams.get('player');
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});
  const [teams, setTeams] = useState<Team[]>([]);
  const [teamId, setTeamId] = useTeamQuery();
  const [board, setBoard] = useState<DevelopmentBoardRow[]>([]);
  const [posFilter, setPosFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [classFilter, setClassFilter] = useState('');
  const [sortBy, setSortBy] = useState<'dps' | 'leverage' | 'mpg' | 'proj_value'>('dps');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.teams().then(setTeams).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!teamId) return;
    setLoading(true);
    setError('');
    api
      .developmentBoard(teamId)
      .then(setBoard)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [teamId]);

  useEffect(() => {
    if (!highlightPlayer || loading) return;
    const row = rowRefs.current[highlightPlayer];
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [highlightPlayer, board, loading]);

  const filtered = useMemo(() => {
    let rows = [...board];
    if (posFilter) rows = rows.filter((r) => r.position === posFilter);
    if (priorityFilter) rows = rows.filter((r) => r.top_priority === priorityFilter);
    if (classFilter) rows = rows.filter((r) => (r.class_year_2026_27 || 'Unknown') === classFilter);
    rows.sort((a, b) => {
      if (sortBy === 'leverage')
        return (b.development_leverage_score ?? 0) - (a.development_leverage_score ?? 0);
      if (sortBy === 'mpg') return b.mpg - a.mpg;
      if (sortBy === 'proj_value')
        return (b.projected_points_added ?? 0) - (a.projected_points_added ?? 0);
      return b.development_priority_score - a.development_priority_score;
    });
    return rows;
  }, [board, posFilter, priorityFilter, classFilter, sortBy]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-4 items-end justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold">Player Development Board</h2>
          <p className="text-gray-400 text-sm">
            Top Priority is chosen by scoring all nine skill areas with the Development Priority Score (DPS), then
            applying an actionable filter. A skill must have a real player opportunity gap, meaningful team need,
            positive projected value, and reasonable position/role fit. If one or more skills pass, the app selects
            the highest adjusted DPS as the player&apos;s Top Priority. Sometimes no skill passes all four checks. That
            can happen when a player is already close to peer level in most areas, when his biggest individual gap
            does not match a team need, when the team need is not realistic for his position, or when the projected
            value is too small to call it a strong recommendation. In those cases, the app still shows the best
            remaining relative focus so the board is not blank. Relative focus means “this is the most relevant
            remaining development area,” not a firm staff recommendation.{' '}
            <Link
              to="/methodology#development-priority-score-dps"
              className="text-illini-orange hover:underline"
            >
              See Methodology
            </Link>{' '}
            for how DPS is calculated (formula, weights, and each component). For Top Priority and the{' '}
            <Link
              to="/methodology#top-priority-actionable-filter"
              className="text-illini-orange hover:underline"
            >
              actionable filter
            </Link>
            , see the Top Priority section in Methodology.
          </p>
        </div>
        <TeamSelect teams={teams} value={teamId} onChange={setTeamId} />
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          value={posFilter}
          onChange={(e) => setPosFilter(e.target.value)}
          className="bg-surface-card border border-surface-border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="">All positions</option>
          <option value="G">Guards</option>
          <option value="F">Forwards</option>
          <option value="C">Centers</option>
        </select>
        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="bg-surface-card border border-surface-border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="">All priorities</option>
          {PRIORITY_OPTIONS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
        <select
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          className="bg-surface-card border border-surface-border rounded-lg px-3 py-1.5 text-sm"
          title="Class reflects projected 2026-27 roster status when available."
        >
          <option value="">All classes</option>
          {CLASS_OPTIONS.map((cls) => (
            <option key={cls} value={cls}>{cls}</option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="bg-surface-card border border-surface-border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="dps">Sort by DPS</option>
          <option value="leverage">Sort by Leverage</option>
          <option value="mpg">Sort by MPG</option>
          <option value="proj_value">Sort by Proj. Value</option>
        </select>
      </div>
      <div className="text-xs text-gray-500 -mt-4 space-y-1">
        <p>
          Class reflects projected 2026-27 roster status when available. Incoming high-school freshmen are not
          included in this player stats baseline.
        </p>
        <p>
          View{' '}
          <Link
            to="/methodology#development-priority-score-dps"
            className="text-illini-orange hover:underline"
          >
            methodology for DPS
          </Link>
          ,{' '}
          <Link
            to="/methodology#projected-value-dev-board"
            className="text-illini-orange hover:underline"
          >
            methodology for Proj. Value
          </Link>
          , and{' '}
          <Link
            to="/methodology#development-leverage-score"
            className="text-illini-orange hover:underline"
          >
            methodology for Leverage
          </Link>
          .
        </p>
      </div>

      {error && <ApiError message={error} />}

      {!loading && board.length > 0 && (
        <div className="grid lg:grid-cols-3 gap-4">
          <ChartCard
            title="Team DPS by player (top-priority skill)"
            caption="Bar height = Development Priority Score for each player's #1 focus skill."
            className="card lg:col-span-2 !bg-surface-card"
          >
            <DevBoardDpsChart board={filtered.length ? filtered : board} />
          </ChartCard>
          <ChartCard title="DPS formula" className="card !bg-surface-card">
            <p className="font-mono text-[11px] text-illini-orange bg-surface/70 rounded px-2 py-1.5 mb-3 leading-relaxed">
              Raw DPS = 0.30×Opportunity + 0.30×Team Need + 0.20×Role (MPG) + 0.10×Realism + 0.10×Impact
              <br />
              Adjusted DPS = Raw DPS × Position Fit
            </p>
            <DpsWeightDonut compact />
          </ChartCard>
        </div>
      )}

      <div className="card overflow-x-auto">
        {loading ? (
          <p className="text-gray-400 py-8 text-center">Loading board…</p>
        ) : (
          <>
            <div className="mb-3 space-y-2 text-xs text-gray-500 leading-relaxed">
              <p>
                <span className="font-medium text-gray-400">Who appears here:</span> Players need a meaningful
                2025–26 sample — at least <span className="text-gray-400">10 MPG</span> or{' '}
                <span className="text-gray-400">250 total minutes</span> — to be scored. The board then applies
                projected <span className="text-gray-400">2026–27 roster status</span>: players who left for the
                transfer portal, transferred out, graduated, or are otherwise no longer on the team are removed
                even if they met that sample last season. Incoming transfers from other D-I programs in the
                tool keep their prior-season baseline and are marked Transfer when applicable. High-school
                freshmen and other players without a college stats baseline are not listed.
              </p>
              <p>
                Click a player&apos;s name to open the full profile with production ranks, advanced context, shot
                profile, strengths/weaknesses, and detailed development priorities. Use the sort dropdown or column
                headers to reorder the board.
              </p>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-400 border-b border-surface-border">
                  <th className="py-2 pr-4">Player</th>
                  <th className="py-2">Pos</th>
                  <th
                    className="py-2"
                    title="Class reflects projected 2026-27 roster status when available."
                  >
                    Class
                  </th>
                  <th className="py-2">MPG</th>
                  <th className="py-2">Top Priority</th>
                  <th className="py-2">DPS</th>
                  <th className="py-2 align-top min-w-[11rem]">
                    <button
                      type="button"
                      onClick={() => setSortBy('proj_value')}
                      className="text-left w-full group"
                      title={PROJ_VALUE_COLUMN_TOOLTIP}
                    >
                      <span
                        className={`block font-semibold ${
                          sortBy === 'proj_value'
                            ? 'text-illini-orange'
                            : 'text-gray-400 group-hover:text-illini-orange'
                        }`}
                      >
                        Proj. Value
                        {sortBy === 'proj_value' ? (
                          <span className="ml-1 text-[10px] font-normal" aria-hidden>
                            ↓ high–low
                          </span>
                        ) : null}
                      </span>
                    </button>
                  </th>
                  <th className="py-2">Leverage</th>
                  <th className="py-2 min-w-[280px]">Main Reason</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr
                    key={row.player_id}
                    ref={(el) => { rowRefs.current[row.player_id] = el; }}
                    className={`table-row-hover border-b border-surface-border/50 ${
                      highlightPlayer === row.player_id
                        ? 'bg-illini-orange/10 ring-1 ring-inset ring-illini-orange'
                        : ''
                    }`}
                  >
                    <td className="py-3 pr-4">
                      <Link to={`/player/${row.player_id}`} className="text-illini-orange font-medium hover:underline">
                        {row.player_name}
                      </Link>
                      {row.is_transfer_in && (
                        <span
                          className="ml-2 text-[10px] uppercase tracking-wide text-gray-500"
                          title={
                            row.transfer_from
                              ? `2026-27 transfer from ${row.transfer_from}`
                              : '2026-27 transfer'
                          }
                        >
                          Transfer
                        </span>
                      )}
                    </td>
                    <td>{row.position}</td>
                    <td>{row.class_year_2026_27 || 'Unknown'}</td>
                    <td>{row.mpg?.toFixed(1)}</td>
                    <td>
                      <span className="badge-orange">
                        {SKILL_LABELS[row.top_priority] || row.top_priority}
                      </span>
                    </td>
                    <td className="font-bold">{row.development_priority_score?.toFixed(1)}</td>
                    <td>+{row.projected_points_added?.toFixed(1)}</td>
                    <td>{row.development_leverage_score?.toFixed(1) ?? '—'}</td>
                    <td className="text-gray-400 text-xs leading-relaxed align-top min-w-[280px] max-w-md whitespace-normal">
                      {row.main_reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {!loading && !filtered.length && !error && (
          <p className="text-gray-500 py-6 text-center">No players match filters.</p>
        )}
      </div>
    </div>
  );
}
