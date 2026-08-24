import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { OverviewData } from '../types';
import { SKILL_LABELS, SKILL_ORDER } from '../types';
import StatCard from '../components/StatCard';
import ApiError from '../components/ApiError';
import {
  DpsWeightDonut,
  TeamNeedsBarChart,
  LeverageBarChart,
} from '../charts/AppCharts';
import NeedsRadar from '../charts/NeedsRadar';
import { FEATURED_TEAM_ID, FEATURED_TEAM_NAME } from '../lib/brand';

const featuredTeamId = FEATURED_TEAM_ID;

export default function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [featuredExplain, setFeaturedExplain] = useState<Record<string, string>>({});

  useEffect(() => {
    api
      .overview()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    api
      .team(featuredTeamId)
      .then((r) => setFeaturedExplain(r.needs?.need_explanations ?? {}))
      .catch(() => {});
  }, []);

  if (loading) return <p className="text-gray-400">Loading overview…</p>;
  if (error) return <ApiError message={error} />;
  if (!data) return <p className="text-red-400">Failed to load overview.</p>;

  const datasetNeedItems = data
    ? (() => {
        const byKey = Object.fromEntries(
          data.top_team_needs.map((n) => [n.category, n.score])
        );
        return [...SKILL_ORDER]
          .map((key) => ({
            key,
            label: SKILL_LABELS[key] || key,
            score: byKey[key] ?? 0,
          }))
          .sort((a, b) => b.score - a.score);
      })()
    : [];

  const featuredNeeds = data.featured_team_needs
    ? Object.entries(data.featured_team_needs)
        .filter(([k]) => k.endsWith('_need'))
        .map(([k, v]) => ({
          key: k.replace('_need', ''),
          score: v as number,
          label: SKILL_LABELS[k.replace('_need', '')] || k,
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 3)
    : [];

  return (
    <div className="space-y-6">
      <section className="card border-l-4 border-illini-orange">
        <h2 className="font-display text-2xl font-bold text-white mb-2">
          Player Development Decision Support
        </h2>
        <p className="text-gray-300 leading-relaxed max-w-3xl mb-3">
          <strong className="text-white">The problem:</strong> College staffs have limited practice time,
          individual workout bandwidth, and film-session capacity. They often know a player is weak in an area,
          but the harder question is operational — which skill should that player work on{' '}
          <em>for this team right now</em>, and whether that improvement would actually matter for the roster.
          Generic stat pages do not connect player gaps to team needs, role, or realistic one-season gains.
        </p>
        <p className="text-gray-300 leading-relaxed max-w-3xl">
          <strong className="text-white">What DevelopmentIQ does:</strong> It is a college basketball
          player-development decision-support tool that identifies which player–skill improvements would create
          the most value by combining player weaknesses, team needs, role/minutes leverage, improvement
          realism, and basketball impact.
        </p>
        <p className="mt-3 text-sm text-illini-orange font-medium">
          Central question: Which skill improvement would create the most value for this player and this team?
        </p>
        <p className="mt-4 text-sm text-gray-300 leading-relaxed max-w-3xl border-t border-surface-border/60 pt-4">
          <strong className="text-white">Example:</strong> If a team struggles on the defensive glass,
          DevelopmentIQ prioritizes rotation players whose{' '}
          <strong className="text-illini-orange">defensive rebounding</strong> improvement would address that
          team weakness because that skill closes a roster gap where
          they have room to grow.
        </p>
      </section>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Teams"
          value={data.teams_count}
          sub={`${data.teams_count} teams — power + mid-major`}
        />
        <StatCard label="Rotation Players" value={data.players_count} sub="Filter of ≥10 MPG or 250 min" accent="blue" />
        <StatCard label="Skill Categories" value={9} sub="Team-relative and player-relative priorities" />
        <StatCard label="Roster" value="2026-27" sub="Uses 2025-26 stats as baseline" accent="blue" />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="card lg:col-span-1 flex flex-col">
          <h3 className="font-display text-lg font-semibold text-illini-orange mb-3">
            Development Priority Score (DPS) weights
          </h3>
          <p className="text-xs text-gray-500 mb-2 leading-relaxed">
            Every rotation player gets nine DPS scores — one per skill (shooting, rebounding, ball security,
            etc.). Player gap and team need matter most; minutes and fixed realism/impact priors add context.
            Each skill gets a <strong className="text-gray-400">position-fit multiplier</strong> (e.g. guards
            downweighted on offensive rebounding) so priorities match role.{' '}
            <strong className="text-gray-400">Top Priority</strong> on the Dev Board is the highest{' '}
            <strong className="text-gray-400">adjusted DPS</strong> across those nine when it passes the
            actionable filter —{' '}
            <Link
              to="/methodology#top-priority-actionable-filter"
              className="text-illini-orange hover:underline"
            >
              See Methodology
            </Link>{' '}
            for the four gates, position-fit multipliers, and fallback rules. If none qualify, the top adjusted
            score is still shown as relative focus.
          </p>
          <p className="font-mono text-[11px] text-illini-orange bg-surface/70 rounded px-2 py-1.5 mb-3 leading-relaxed">
            Raw DPS = 0.30×Opportunity + 0.30×Team Need + 0.20×Role (MPG) + 0.10×Realism + 0.10×Impact
            <br />
            Adjusted DPS = Raw DPS × Position Fit
          </p>
          <DpsWeightDonut compact />
        </div>

        <div className="card lg:col-span-1 flex flex-col">
          <h3 className="font-display text-lg font-semibold text-illini-orange mb-3">
            Team Needs — All 9 Skills (Dataset Average)
          </h3>
          <p className="text-xs text-gray-500 mb-3 leading-relaxed">
            Average need score for each of the nine skill areas across all {data.teams_count} teams (not one school).
            Higher bars = relatively more common roster weakness in this pool (0–100).{' '}
            <Link
              to="/methodology#team-needs-map-skillset"
              className="text-illini-orange hover:underline"
            >
              See Methodology
            </Link>{' '}
            for Team Need Score formulas ·{' '}
            <Link to="/team-needs" className="text-illini-orange hover:underline">
              Team Needs Map
            </Link>{' '}
            for one program&apos;s ranked needs.
          </p>
          <TeamNeedsBarChart items={datasetNeedItems} limit={9} />
        </div>

        <div className="card lg:col-span-1 flex flex-col">
          <h3 className="font-display text-lg font-semibold text-illini-orange mb-3">
            Development Leverage Leaders
          </h3>
          <p className="text-xs text-gray-500 mb-2 leading-relaxed">
            One whole-player score per rotation player (not per skill). It ranks who is the best overall
            development investment. Use this to see who has the clearest high-value pathway on the roster.{' '}
            <Link
              to="/methodology#development-leverage-score"
              className="text-illini-orange hover:underline"
            >
              See Methodology
            </Link>{' '}
            for how Development Leverage is calculated (production, upside, need match, minutes, class runway).
          </p>
          <p className="font-mono text-[11px] text-illini-orange bg-surface/70 rounded px-2 py-1.5 mb-3 leading-relaxed">
            Leverage = 0.30×Production + 0.30×Upside + 0.20×Need match + 0.10×Minutes + 0.10×Class runway
          </p>
          <LeverageBarChart
            items={data.top_leverage_players.slice(0, 8).map((p) => ({
              name: p.player_name,
              score: p.development_leverage_score ?? 0,
              sub: p.team_name,
            }))}
            limit={8}
          />
          <Link to="/leaderboard" className="inline-block mt-4 text-sm text-illini-orange hover:underline">
            View full leaderboard →
          </Link>
        </div>
      </div>

      <section className="card bg-illini-blue/40 border-illini-orange/30">
        <h3 className="font-display text-xl font-bold mb-2">
          <span className="text-illini-orange">{FEATURED_TEAM_NAME}</span>
        </h3>
        <p className="text-gray-300 text-sm mb-4">
          Explore how team needs shape player development priorities for this program.
        </p>
        {featuredNeeds.length > 0 && (
          <div className="grid md:grid-cols-2 gap-4 mb-4">
            <div>
              <h4 className="text-sm text-gray-400 mb-2">Needs radar</h4>
              {data.featured_team_needs && (
                <NeedsRadar needs={data.featured_team_needs as Record<string, number>} />
              )}
            </div>
            <div>
              <h4 className="text-sm text-gray-400 mb-2">Top 3 needs (ranked)</h4>
              <TeamNeedsBarChart items={featuredNeeds} limit={3} />
              <ul className="mt-3 space-y-2 text-sm">
                {featuredNeeds.map((n, i) => (
                  <li key={n.key} className="text-gray-400 text-xs leading-relaxed">
                    <span className="text-illini-orange font-semibold">{i + 1}. {n.label}</span> —{' '}
                    {featuredExplain[n.key] || 'See Team Needs Map for stat-backed detail.'}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <Link to={`/team-needs?team=${featuredTeamId}`} className="btn-primary text-sm">
            Team Needs Map
          </Link>
          <Link to={`/development-board?team=${featuredTeamId}`} className="btn-secondary text-sm">
            Development Board
          </Link>
        </div>
      </section>
    </div>
  );
}
