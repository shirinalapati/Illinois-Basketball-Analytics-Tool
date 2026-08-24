import type { ReactNode } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import ChartCard from './ChartCard';
import { DpsWeightCard } from './AppCharts';
import { axisTick, BLUE, categoryTick, CHART_BLUE_SOFT, MUTED, ORANGE, tooltipProps } from './chartTheme';
import { SKILL_LABELS, SKILL_RADAR_LABELS } from '../types';

function ChartBox({ title, caption, children }: { title: string; caption?: string; children: ReactNode }) {
  return (
    <ChartCard title={title} caption={caption} className="my-3">
      {children}
    </ChartCard>
  );
}

/** DPS formula weights */
export function DpsWeightChart() {
  return <DpsWeightCard />;
}

/** End-to-end model flow */
export function ModelFlowChart() {
  const steps = [
    { label: 'Team stats', sub: '103 teams', color: BLUE },
    { label: 'Player stats', sub: 'Rotation pool', color: BLUE },
    { label: 'Team need', sub: '9 skills × team', color: ORANGE },
    { label: 'Opportunity', sub: '9 skills × player', color: ORANGE },
    { label: 'DPS', sub: '9 rows / player', color: ORANGE },
    { label: 'Top priority', sub: '1 label / player', color: CHART_BLUE_SOFT },
    { label: 'Leverage', sub: '1 score / player', color: MUTED },
  ];
  return (
    <ChartBox title="How data flows through the model" caption="Computed at seed time; API serves pre-calculated scores.">
      <div className="flex flex-wrap items-center gap-1 justify-center py-2">
        {steps.map((s, i) => (
          <div key={s.label} className="flex items-center gap-1">
            <div
              className="rounded-lg px-3 py-2 text-center min-w-[88px] border border-surface-border"
              style={{ borderColor: s.color }}
            >
              <p className="text-xs font-semibold text-white">{s.label}</p>
              <p className="text-[10px] text-gray-400">{s.sub}</p>
            </div>
            {i < steps.length - 1 ? (
              <span className="text-illini-orange text-lg px-0.5" aria-hidden>
                →
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </ChartBox>
  );
}

const OPP_STAT_DETAILS: Record<string, { stats: string; invert: boolean }> = {
  shooting: { stats: '3P%, eFG%, 3PA rate, 3PA', invert: false },
  free_throw: { stats: 'FT%, FTr, FTA, rim rate', invert: false },
  ball_security: { stats: 'TOV%, AST/TOV, usage', invert: true },
  defensive_rebounding: { stats: 'DRB rate, DBPM, MPG', invert: false },
  offensive_rebounding: { stats: 'ORB rate, position', invert: false },
  foul_discipline: { stats: 'Foul rate, fouls/40, MPG', invert: true },
  playmaking: { stats: 'Assist rate, AST/TOV, usage, position', invert: false },
  defensive_activity: { stats: 'Steal rate/%, block rate/%, DBPM', invert: false },
  rim_pressure: { stats: 'Rim FG%, rim rate, FTr, TS%', invert: false },
};

const OPP_STATS = (
  [
    'shooting',
    'free_throw',
    'ball_security',
    'defensive_rebounding',
    'offensive_rebounding',
    'foul_discipline',
    'playmaking',
    'defensive_activity',
    'rim_pressure',
  ] as const
).map((key) => ({
  skill: SKILL_RADAR_LABELS[key],
  ...OPP_STAT_DETAILS[key],
}));

/** Player improvement opportunity formula */
export function OpportunityHeuristicChart() {
  return (
    <ChartBox title="Player Improvement Opportunity — formula">
      <div className="space-y-3 text-xs text-gray-400">
        <p className="font-mono text-illini-orange">
          For each skill: Gap_pos = max(0, peer_median − player) · Gap_pool = max(0, field_median − player)
        </p>
        <p className="font-mono text-illini-orange">
          Raw = average(Gap_pos, Gap_pool) per stat · then Opportunity = min-max normalize across all players
        </p>
        <p>
          <strong className="text-gray-300">Higher-is-worse stats</strong> (turnovers, fouls): flip to{' '}
          <strong className="text-gray-300">max(0, player − median)</strong> so being worse than peers raises
          opportunity.
        </p>
      </div>
      <div className="grid grid-cols-3 gap-1.5 mt-3 text-[10px]">
        {OPP_STATS.map((r) => (
          <div
            key={r.skill}
            className="rounded border border-surface-border bg-surface/60 px-2 py-1.5"
          >
            <p className="text-gray-300 font-semibold">{r.skill}</p>
            <p className="text-illini-orange font-mono">{r.stats}</p>
            {r.invert ? <p className="text-gray-500">higher = more opp</p> : null}
          </div>
        ))}
      </div>
    </ChartBox>
  );
}

const REALISM_DATA = [
  { skill: SKILL_RADAR_LABELS.free_throw, score: 100 },
  { skill: SKILL_RADAR_LABELS.shooting, score: 90 },
  { skill: SKILL_RADAR_LABELS.rim_pressure, score: 80 },
  { skill: SKILL_RADAR_LABELS.playmaking, score: 70 },
  { skill: SKILL_RADAR_LABELS.ball_security, score: 60 },
  { skill: SKILL_RADAR_LABELS.defensive_rebounding, score: 50 },
  { skill: SKILL_RADAR_LABELS.foul_discipline, score: 40 },
  { skill: SKILL_RADAR_LABELS.offensive_rebounding, score: 30 },
  { skill: SKILL_RADAR_LABELS.defensive_activity, score: 20 },
].reverse();

export function RealismBarChart() {
  return (
    <ChartBox
      title="Improvement Realism scores (YoY calibration)"
      caption="235 same-school returners · scaled 20–100"
    >
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={REALISM_DATA} layout="vertical" margin={{ left: 4, right: 12 }}>
          <XAxis type="number" domain={[0, 100]} tick={axisTick} />
          <YAxis type="category" dataKey="skill" tick={categoryTick} width={100} />
          <Tooltip {...tooltipProps} />
          <Bar dataKey="score" name="Realism" fill={ORANGE} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

const FOUR_FACTORS = [
  { name: 'eFG% (shooting / rim)', pts: 40, fill: ORANGE },
  { name: 'TOV% (ball security)', pts: 25, fill: BLUE },
  { name: 'ORB% (off. rebounding)', pts: 20, fill: MUTED },
  { name: 'FTR (FT / rim)', pts: 15, fill: CHART_BLUE_SOFT },
];

export function FourFactorsChart() {
  return (
    <ChartBox title="Dean Oliver Four Factors → impact raw points" caption="Offensive four factors sum to 100 pts before scaling to 20–100 impact scores.">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={FOUR_FACTORS} margin={{ bottom: 48 }}>
          <XAxis dataKey="name" tick={{ ...axisTick, fontSize: 9 }} angle={-12} textAnchor="end" height={56} />
          <YAxis tick={axisTick} label={{ value: 'Raw pts', angle: -90, position: 'insideLeft', fill: axisTick.fill, fontSize: 10 }} />
          <Tooltip {...tooltipProps} />
          <Bar dataKey="pts" name="Weight" radius={[4, 4, 0, 0]}>
            {FOUR_FACTORS.map((d, i) => (
              <Cell key={i} fill={d.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

const IMPACT_DATA = [
  { skill: SKILL_RADAR_LABELS.ball_security, score: 100 },
  { skill: SKILL_RADAR_LABELS.shooting, score: 95 },
  { skill: SKILL_RADAR_LABELS.rim_pressure, score: 93 },
  { skill: SKILL_RADAR_LABELS.offensive_rebounding, score: 77 },
  { skill: SKILL_RADAR_LABELS.defensive_rebounding, score: 50 },
  { skill: SKILL_RADAR_LABELS.playmaking, score: 36 },
  { skill: SKILL_RADAR_LABELS.defensive_activity, score: 31 },
  { skill: SKILL_RADAR_LABELS.foul_discipline, score: 22 },
  { skill: SKILL_RADAR_LABELS.free_throw, score: 20 },
].reverse();

export function ImpactBarChart() {
  return (
    <ChartBox title="Basketball Impact scores (Four Factors)" caption="Higher = skill type usually matters more for team efficiency.">
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={IMPACT_DATA} layout="vertical" margin={{ left: 4, right: 12 }}>
          <XAxis type="number" domain={[0, 100]} tick={axisTick} />
          <YAxis type="category" dataKey="skill" tick={categoryTick} width={100} />
          <Tooltip {...tooltipProps} />
          <Bar dataKey="score" name="Impact" fill={ORANGE} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}

/** 3P% target = min(current + 5%, ceiling) */
type TargetRow = { label: string; current: number; target: number; ceiling: number };

function TargetScenarioBars({ rows }: { rows: TargetRow[] }) {
  return (
    <div className="space-y-4">
      {rows.map((r) => {
        const gap = Math.max(0, r.target - r.current);
        return (
          <div key={r.label}>
            <p className="text-xs text-gray-400 mb-1">{r.label}</p>
            <div className="relative h-8 bg-surface rounded overflow-hidden border border-surface-border">
              <div
                className="absolute top-0 bottom-0 bg-sky-900/40 border-r border-sky-500/50"
                style={{ left: 0, width: `${r.ceiling * 100}%` }}
                title={`Ceiling ${(r.ceiling * 100).toFixed(1)}%`}
              />
              <div
                className="absolute top-1 bottom-1 bg-slate-500 rounded-sm"
                style={{ left: 0, width: `${r.current * 100}%` }}
                title={`Current ${(r.current * 100).toFixed(1)}%`}
              />
              <div
                className="absolute top-1 bottom-1 bg-illini-orange rounded-sm opacity-90"
                style={{ left: `${r.current * 100}%`, width: `${gap * 100}%` }}
                title={`Gain ${(gap * 100).toFixed(1)}%`}
              />
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-illini-orange"
                style={{ left: `${r.target * 100}%` }}
              />
            </div>
            <p className="text-[10px] text-gray-400 mt-0.5 font-mono">
              Current {(r.current * 100).toFixed(0)}% → Target {(r.target * 100).toFixed(1)}% (gap{' '}
              {(gap * 100).toFixed(1)}%) · Ceiling {(r.ceiling * 100).toFixed(1)}%
            </p>
          </div>
        );
      })}
      <div className="flex gap-4 text-[10px] text-gray-400">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-2 bg-slate-500 rounded-sm" /> Current
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-2 bg-illini-orange rounded-sm" /> Projected gain
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-4 bg-sky-900/40 border border-sky-500/50" /> Ceiling zone
        </span>
      </div>
    </div>
  );
}

export function ProjectionTargetChart() {
  const rows: TargetRow[] = [
    { label: 'Player A — room for full +5%', current: 0.32, target: 0.37, ceiling: 0.413 },
    { label: 'Player B — ceiling trims bump', current: 0.38, target: 0.413, ceiling: 0.413 },
    { label: 'Player C — almost no gain', current: 0.41, target: 0.413, ceiling: 0.413 },
  ];
  return (
    <ChartBox
      title={`Target = min(current + 5%, 41.3% ceiling) — ${SKILL_LABELS.shooting}`}
      caption="Orange = points gained in the model. Gap = target − current (not ceiling − current)."
    >
      <TargetScenarioBars rows={rows} />
    </ChartBox>
  );
}

export function TopPriorityFlowChart() {
  return (
    <ChartBox title="How Top Priority is chosen">
      <div className="flex flex-col gap-2 text-sm">
        <div className="rounded-lg border border-illini-orange/40 bg-illini-orange/10 px-4 py-3 text-center">
          <p className="font-semibold text-white">All 9 skills scored (DPS each)</p>
        </div>
        <p className="text-center text-illini-orange">↓</p>
        <div className="rounded-lg border border-surface-border bg-surface px-4 py-3">
          <p className="font-semibold text-gray-200">Filter: actionable?</p>
          <p className="text-xs text-gray-500 mt-1">
            Real opportunity · team need · proj. &gt; 0 · position fit · then highest adjusted DPS
          </p>
        </div>
        <p className="text-center text-illini-orange">↓</p>
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-green-500/30 bg-green-950/20 px-3 py-2 text-center">
            <p className="text-xs font-semibold text-green-300">Some qualify</p>
            <p className="text-[10px] text-gray-500">→ Actionable focus · highest DPS</p>
          </div>
          <div className="rounded-lg border border-gray-500/30 bg-surface px-3 py-2 text-center">
            <p className="text-xs font-semibold text-gray-300">None qualify</p>
            <p className="text-[10px] text-gray-500">→ Relative focus · opp &gt; 0, prefer ≥ 10</p>
          </div>
        </div>
      </div>
    </ChartBox>
  );
}

export function LeverageWeightChart() {
  const data = [
    { name: 'Production', pct: 30, fill: ORANGE },
    { name: 'Upside', pct: 30, fill: BLUE },
    { name: 'Need match', pct: 20, fill: MUTED },
    { name: 'Minutes', pct: 10, fill: CHART_BLUE_SOFT },
    { name: 'Class runway', pct: 10, fill: '#cbd5e1' },
  ];
  return (
    <ChartBox title="Development Leverage weights (whole player)">
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical" margin={{ left: 8 }}>
          <XAxis type="number" domain={[0, 35]} tick={axisTick} unit="%" />
          <YAxis type="category" dataKey="name" tick={{ ...categoryTick, fontSize: 11 }} width={88} />
          <Tooltip {...tooltipProps} formatter={(v: number) => [`${v}%`, 'Weight']} />
          <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartBox>
  );
}
