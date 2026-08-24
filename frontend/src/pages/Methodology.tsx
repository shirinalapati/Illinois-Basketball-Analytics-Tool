import type { ReactNode } from 'react';
import { MethodologyAccordion } from '../components/MethodologyAccordion';
import {
  PROJECTED_VALUE_SUMMARY,
  DEV_BOARD_PROJ_VALUE_HEADLINE,
  REALISTIC_TARGET_CALIBRATION,
  RECOMMENDED_SCENARIO_LABEL,
} from '../lib/projectionCopy';
import {
  NINE_SKILL_NAMES_LIST,
  PROJ_VALUE_EXAMPLE_BY_SKILL,
  REALISTIC_TARGET_BY_SKILL,
  SKILL_LABELS,
  SKILL_ORDER,
} from '../types';
import {
  DpsWeightChart,
  ModelFlowChart,
  RealismBarChart,
  ImpactBarChart,
  LeverageWeightChart,
} from '../charts/MethodologyVisuals';

function DetailBox({ children }: { children: ReactNode }) {
  return (
    <span className="block rounded-lg border border-surface-border bg-surface/50 px-3 py-2 text-gray-400 not-italic space-y-2">
      {children}
    </span>
  );
}

const GLOSSARY = [
  {
    term: 'Development Priority Score (DPS)',
    def: 'How valuable it would be for this player to improve this specific skill for this team (0–100). Uses adjusted DPS = raw score × position fit so guards are not steered toward big-man skills unless they have a real gap.',
  },
  {
    term: 'Team Need Score',
    def: 'How badly the team needs improvement in that area relative to the 103-team pool (0 = relative strength, 100 = biggest weakness in the pool). This is a team-level score for each skill area — not a player score and not Development Leverage. To see whether the current roster can address a high need, check whether any rotation player has actionable DPS (Top Priority with actionable focus) in that skill. If team need is severe but nobody does, the gap may require portal, recruiting, or lineup-construction — not internal development alone.',
  },
  {
    term: 'Player Opportunity',
    def: 'How much room the player has to improve in that skill relative to position peers and the full rotation pool (0–100, normalized).',
  },
  {
    term: 'Projected Value',
    def: PROJECTED_VALUE_SUMMARY,
  },
  {
    term: 'Development Leverage',
    def: 'One whole-player score per rotation player (0–100), not per skill. It ranks who is the best overall development investment on the roster by blending production, upside (average DPS on top three skills), team-need match on those skills, minutes, and class-year runway. There is no Development Leverage score by skill — use DPS for skill-level priorities.',
  },
  {
    term: 'Top Priority',
    def: 'The #1 development skill on the Dev Board and Player Profile. Chosen only from skills that pass the actionable filter when possible (real player opportunity, team need, positive projected value, and reasonable position fit). If none qualify, the app shows the best remaining skill as a relative focus — not a strong development recommendation.',
  },
  {
    term: 'Actionable focus vs relative focus',
    def: 'Actionable focus (blue badge) means the skill passes all four gates and is a strong recommendation. Relative focus (limited gap) means no skill cleared the actionable bar; the label still ranks skills by gap and DPS but should be read as directional, not a firm staff mandate.',
  },
  {
    term: 'Nine skill categories',
    def: `Every screen uses the same labels: ${NINE_SKILL_NAMES_LIST}. Team-level inputs are summarized under Team Needs Map Skillset.`,
  },
];

const TEAM_NEED_FORMULAS: Record<(typeof SKILL_ORDER)[number], string> = {
  shooting: 'Raw = mean((1 − 3P%) × 100, (1 − eFG%) × 60, (1 − 3PA rate) × 60)',
  free_throw: 'Raw = (1 − FT%) × 100',
  ball_security: 'Raw = turnover rate × 400',
  defensive_rebounding: 'Raw = (1 − defensive rebounding rate) × 120',
  offensive_rebounding: 'Raw = (1 − offensive rebounding rate) × 120',
  foul_discipline: 'Raw = foul rate × 350',
  playmaking: 'Raw = (1 − assist rate) × 100',
  defensive_activity: 'Raw = mean(steal weakness, block weakness, defensive-rating weakness)',
  rim_pressure: 'Raw = mean((1 − rim attempt rate) × 80, (1 − rim FG%) × 70, (1 − FTr) × 60)',
};

const TEAM_NEED_SKILLSET = SKILL_ORDER.map((key) => ({
  skill: SKILL_LABELS[key],
  formula: TEAM_NEED_FORMULAS[key],
}));

const POSITION_FIT_ROWS: {
  skill: (typeof SKILL_ORDER)[number];
  g: string;
  f: string;
  c: string;
}[] = [
  { skill: 'shooting', g: '1.00', f: '1.00', c: '0.90' },
  { skill: 'ball_security', g: '1.00', f: '0.90', c: '0.75' },
  { skill: 'playmaking', g: '1.00', f: '0.85', c: '0.65' },
  { skill: 'offensive_rebounding', g: '0.65', f: '0.85', c: '1.00' },
  { skill: 'defensive_rebounding', g: '0.75', f: '0.90', c: '1.00' },
  { skill: 'foul_discipline', g: '0.80', f: '0.90', c: '1.00' },
  { skill: 'defensive_activity', g: '0.90', f: '1.00', c: '0.95' },
  { skill: 'rim_pressure', g: '0.90', f: '0.95', c: '1.00' },
];

const IMPACT_RAW_EXAMPLE_ROWS: {
  skill: (typeof SKILL_ORDER)[number];
  raw: string;
  impact: string;
}[] = [
  { skill: 'ball_security', raw: '25', impact: '100' },
  { skill: 'shooting', raw: '24', impact: '95' },
  { skill: 'rim_pressure', raw: '23.5', impact: '93' },
  { skill: 'offensive_rebounding', raw: '20', impact: '77' },
  { skill: 'defensive_rebounding', raw: '14', impact: '50' },
  { skill: 'playmaking', raw: '11', impact: '36' },
  { skill: 'defensive_activity', raw: '10', impact: '31' },
  { skill: 'foul_discipline', raw: '8', impact: '22' },
  { skill: 'free_throw', raw: '7.5', impact: '20' },
];

export default function Methodology() {
  return (
    <div className="space-y-6 max-w-4xl">
      <header>
        <h2 className="font-display text-3xl font-bold">
          Methodology & <span className="text-illini-orange">Documentation</span>
        </h2>
        <p className="text-gray-400 mt-2 text-sm">
          Plain-language overview first — expand any section below for formulas, charts, and audit detail.
        </p>
      </header>

      {/* How to Read the App */}
      <section className="card">
        <h3 className="font-display text-lg font-semibold text-illini-orange mb-4">How to Read the App</h3>
        <dl className="space-y-4">
          {GLOSSARY.map(({ term, def }) => (
            <div key={term}>
              <dt className="font-semibold text-white text-sm">{term}</dt>
              <dd className="text-gray-400 text-sm mt-1 leading-relaxed">{def}</dd>
            </div>
          ))}
        </dl>
        <p className="text-sm text-gray-500 mt-4 leading-relaxed border-t border-surface-border pt-4">
          <strong className="text-gray-400">DPS vs Development Leverage:</strong> DPS is computed for all nine
          skills on every player. Development Leverage is a separate, whole-player ranking — not a per-skill score.
        </p>
      </section>

      <MethodologyAccordion title="Advanced stats & role context" defaultOpen>
        <p className="text-gray-300 leading-relaxed text-sm">
          DevelopmentIQ uses rate-based and possession-aware indicators rather than relying only on raw
          box-score totals. Every player is scored with the same derived inputs: assist-to-turnover ratio, free
          throw rate, two-point percentage, 3PA rate, steal/block activity rates, fouls per 40, and
          position-weighted rebounding and defensive gaps.
        </p>
        <p className="text-gray-500 text-xs leading-relaxed mt-2">
          BPM, PER, and Win Shares are used because the player pool has
          full advanced-stat coverage.
        </p>
        <p className="text-gray-500 text-xs leading-relaxed mt-2">
          <strong className="text-gray-400">Rim Pressure / Finishing</strong> (rim_pressure) — The current player
          pool has full shot-profile coverage, so player opportunity uses tracked rim FG%, rim attempt rate,
          free throw rate, and TS%. Team need uses team rim attempt rate and team rim FG%, aggregated from tracked
          player rim attempts/makes.
        </p>
      </MethodologyAccordion>

      <MethodologyAccordion title="Team Needs Map Skillset" defaultOpen id="team-needs-map-skillset">
        <p>
          The <strong className="text-white">Team Needs Map</strong> scores each team across the same nine skill
          areas. Each raw weakness is calculated from team-level rates, then normalized 0–100 across the 103-team
          pool: <strong className="text-white">0</strong> = relative strength,{' '}
          <strong className="text-white">100</strong> = biggest weakness in the pool.
        </p>
        <p className="text-sm text-gray-400 leading-relaxed">
          Out of all these 9 scores, the highest Need Score for a team represents its biggest relative weakness,
          so the Team Needs Map ranks the nine categories from most important need to least important need for that
          roster based on the numerical values of all the 9 skills.
        </p>
        <p className="text-xs text-gray-500">
          These are the simple Team Needs formulas. The longer player-opportunity, projected-value, and DPS details
          are saved for the technical writeup.
        </p>
        <p className="font-mono text-xs text-illini-orange bg-surface/70 rounded px-3 py-2">
          Need score = min-max normalize raw weakness across the 103-team pool → 0–100
        </p>
        <div className="grid gap-2">
          {TEAM_NEED_SKILLSET.map(({ skill, formula }, index) => (
            <div key={skill} className="rounded-lg border border-surface-border bg-surface/40 px-3 py-2">
              <p className="text-sm font-semibold text-white">
                <span className="text-illini-orange">{index + 1}. {skill}</span>
              </p>
              <p className="font-mono text-xs text-gray-400 mt-1">{formula}</p>
            </div>
          ))}
        </div>
      </MethodologyAccordion>

      <p className="text-xs text-gray-500 uppercase tracking-wide">Technical detail — expand any section</p>

      <MethodologyAccordion title="What Data Was Used">
        <p>
          DevelopmentIQ uses public college basketball team and player statistics from the{' '}
          <strong className="text-white">2025–26 season</strong> as the baseline. These stats describe each
          player&apos;s most recent college role, production, efficiency, and rate profile.
        </p>
        <p>
          The app is built around <strong className="text-white">projected 2026–27 roster assignments</strong>.
          Returning players and transfers are assigned to their expected 2026–27 teams when that information is
          available. Players marked as transferred out, NBA draft departures, or otherwise no longer on a college
          roster are removed from the scored player pool.
        </p>
        <p className="text-sm text-gray-400 mt-2">
          Data comes from public college basketball stat sources, including Sports Reference team and player pages,
          publicly available roster/transfer reporting, and public draft/returning-player updates.
        </p>
      </MethodologyAccordion>

      <MethodologyAccordion title="How the Model Works">
        <p>
          The model runs <strong className="text-white">once per player, per skill</strong> (nine categories).
          Each row gets five inputs of Player Opportunity, Team Need, Role/Minutes, Improvement Realism, and Basketball Impact (0–100), then a Development Priority Score (DPS). The Dev Board shows the
          player&apos;s <strong className="text-white">top priority skill</strong> — the actionable skill with
          the highest DPS when one exists.
        </p>
        <ModelFlowChart />
        <p>
          <strong className="text-gray-300">Nine skill categories:</strong> {NINE_SKILL_NAMES_LIST} (internal ids
          such as rim_pressure map to these display names).
        </p>
        <p className="text-gray-500 text-xs">
          Full formulas for DPS components, team needs, opportunity, projected value, and leverage are in the
          sections below.
        </p>
      </MethodologyAccordion>

      <MethodologyAccordion
        title="Development Priority Score (DPS)"
        id="development-priority-score-dps"
        hashTargets={['top-priority-actionable-filter']}
      >
        <p className="font-mono text-xs text-illini-orange bg-surface/80 rounded px-3 py-2">
          Raw DPS = 0.30×Opportunity + 0.30×Team Need + 0.20×Role + 0.10×Realism + 0.10×Impact
        </p>
        <p className="font-mono text-xs text-illini-orange">
          Adjusted DPS = Raw DPS × Position Fit Multiplier (ranking uses adjusted score)
        </p>
        <DpsWeightChart />

        <div className="space-y-4">
          <div>
            <h4 className="font-semibold text-white mb-2">Player Improvement Opportunity (30%)</h4>
            <p>
              How far the player is below peers (or above, for turnovers/fouls) in that skill. Built from
              position median and pool median gaps on the relevant stats, then normalized 0–100 across all
              rotation players. If core stats for a skill are missing, opportunity stays at 0 (not a neutral
              placeholder) and scales down with a confidence factor when only some inputs are present.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Team Need Alignment (30%)</h4>
            <p>
              How weak the <em>team</em> is in that skill from team efficiency stats (same scores as Team Needs
              Map). Each skill uses team rates (turnover %, rebound %, assist rate, etc.), normalized 0–100
              across 103 teams.
            </p>
            <DetailBox>
              <p className="text-xs text-gray-400">
                Team Need is calculated in two steps:
              </p>
              <p className="font-mono text-xs text-illini-orange">
                Step 1: Raw weakness = skill-specific team stat gap
              </p>
              <p className="font-mono text-xs text-illini-orange">
                Step 2: Need = (Raw − min Raw) / (max Raw − min Raw) × 100
              </p>
              <p className="text-xs text-gray-500">
                Min/max Raw come from the 103-team pool for that skill. A score of 0 means relative strength; 100
                means the biggest weakness in the pool.
              </p>
            </DetailBox>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Minutes / Role Leverage (20%)</h4>
            <p>
              How much development matters because the player is on the floor. Same value for all nine skills
              for that player.
            </p>
            <DetailBox>
              <p className="font-mono text-xs text-illini-orange">
                Role Leverage = min(100, MPG ÷ max MPG in dataset × 100)
              </p>
              <p>
                <strong className="text-gray-300">Examples</strong> (if max MPG = 35): 32 MPG → ≈ 91 · 22 MPG →
                ≈ 63 · 12 MPG → ≈ 34. A starter&apos;s gap is weighted higher than a deep bench player&apos;s
                gap. This is playing time only — not usage rate or star power.
              </p>
            </DetailBox>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Improvement Realism (10%)</h4>
            <p>
              How easy a one-year jump is for that skill type. Same number for every player and every team.
            </p>
            <DetailBox>
              <p>
                Improvement Realism measures how realistic a one-season jump is for each skill.
              </p>
              <p>
                To estimate this, DevelopmentIQ compares 235 returning rotation players from 2024–25 to 2025–26.
                For each skill, the model looks at the median year-over-year change among players who stayed with
                the same school and played at least 10 MPG in both seasons. Skills that commonly improve from year
                to year receive higher realism scores, while skills that are less likely to change quickly receive
                lower realism scores.
              </p>
              <RealismBarChart />
            </DetailBox>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">Basketball Impact Value (10%)</h4>
            <p>
              How much that skill usually matters for winning. Same for everyone — only the skill changes.
              Mapped from Dean Oliver&apos;s Four Factors (offensive) plus secondary weights for defense,
              playmaking, and fouls.
            </p>
            <DetailBox>
              <p>
                Mapped to Dean Oliver&apos;s <strong className="text-gray-300">Four Factors</strong> for team
                offense — eFG% (40%), turnover rate (25%), offensive rebounding (20%), free-throw rate (15%) —
                then scaled to 0–100. Defensive rebounding, playmaking, defensive activity, and foul discipline
                use smaller secondary weights. Each skill gets a raw point total, then all nine are scaled to
                20–100.
              </p>
              <p className="text-sm text-gray-400">
                Offensive four factors sum to 100 pts before scaling to 20–100 impact scores.
              </p>
              <ImpactBarChart />
              <p className="text-xs font-mono text-illini-orange space-y-1">
                <span className="block text-gray-400 not-italic font-sans">
                  <strong className="text-gray-300">Example — Ball security → 100:</strong>
                </span>
                <span className="block">Step 1: Map to turnover factor → raw = 25 (full 25% weight)</span>
                <span className="block">
                  Step 2: Scale all skills — Impact = 20 + (raw − 8) / (25 − 8) × 80 ={' '}
                  <strong className="text-white">100</strong>
                </span>
              </p>
              <p className="text-xs text-gray-500">
                Other examples: {SKILL_LABELS.shooting} raw 24 (60% of eFG&apos;s 40) → 95 ·{' '}
                {SKILL_LABELS.free_throw} raw 7.5 (half of FTR&apos;s 15) → 20 · {SKILL_LABELS.foul_discipline} raw 8
                (secondary) → 22
              </p>
              <table className="w-full text-xs font-mono text-illini-orange">
                <thead>
                  <tr className="text-gray-500 border-b border-surface-border">
                    <th className="text-left font-sans font-normal pb-1">Skill</th>
                    <th className="text-right font-sans font-normal pb-1">Raw pts</th>
                    <th className="text-right font-sans font-normal pb-1">Impact</th>
                  </tr>
                </thead>
                <tbody>
                  {IMPACT_RAW_EXAMPLE_ROWS.map((row) => (
                    <tr key={row.skill}>
                      <td className="text-gray-400 pr-2">{SKILL_LABELS[row.skill]}</td>
                      <td className="text-right text-gray-500">{row.raw}</td>
                      <td className="text-right">{row.impact}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DetailBox>
          </div>
        </div>

        <div id="top-priority-actionable-filter" className="border-t border-surface-border pt-4 mt-4 scroll-mt-24">
          <h4 className="font-semibold text-white mb-2">Top Priority (Dev Board label)</h4>
          <p className="text-gray-400 mb-3">
            The model applies an <strong className="text-gray-300">actionable filter</strong> before assigning a top
            priority. A skill must show a real player opportunity gap (the 0-100 Player Improvement Opportunity
            score shown on the Player Profile), meaningful team need, positive projected value, and reasonable
            position fit. Only then is it labeled{' '}
            <strong className="text-gray-300">Actionable focus</strong> on the Player Profile. If no skill passes,
            the app still surfaces a #1 skill for ranking context but marks it{' '}
            <strong className="text-gray-300">Relative focus (limited gap)</strong> — not a strong development
            recommendation.
          </p>
          <ol className="list-decimal pl-5 space-y-2 text-gray-400">
            <li>
              <strong className="text-gray-300">Actionable filter</strong> — all four must pass: Player Improvement
              Opportunity ≥ 20 (≥ 40 when position fit &lt; 0.80), team need ≥ 40, projected points &gt; 0, position
              fit ≥ 0.65. Among qualifiers, highest <strong className="text-gray-300">adjusted DPS</strong> wins.
            </li>
            <li>
              <strong className="text-gray-300">Fallback (limited gap)</strong> — if none are actionable, rank only
              skills with Player Improvement Opportunity &gt; 0. Prefer opportunity ≥ 10 by adjusted DPS; if none reach
              10, use the highest opportunity skill. Skills with opportunity ≤ 0 cannot become top priority (prevents
              volume-only labels such as elite shooters with zero shooting gap).
            </li>
          </ol>
          <DetailBox>
            <p>
              <strong className="text-gray-300">Why four gates?</strong> Stops team need alone from crowning a skill
              the player cannot realistically emphasize (e.g. guard offensive rebounding without a glass gap, or
              {SKILL_LABELS.shooting} when opportunity is 0 but projected points looked high on volume).
            </p>
            <p className="text-xs text-gray-500 mt-2">
              <strong className="text-gray-300">Position fit example:</strong> Guards use 0.65× on offensive
              rebounding and 1.00× on shooting/playmaking. Even if a team has a big offensive rebounding need, the
              model should not automatically recommend offensive rebounding for every player on that team. For guards,
              offensive rebounding is usually not their main role, so the model lowers the DPS for offensive rebounding
              with a 0.65 position-fit multiplier.
            </p>
            <table className="w-full text-[10px] font-mono mt-2">
              <thead>
                <tr className="text-gray-500 border-b border-surface-border">
                  <th className="text-left font-sans font-normal pb-1">Skill</th>
                  <th className="text-center font-sans font-normal pb-1">Guards</th>
                  <th className="text-center font-sans font-normal pb-1">Wings</th>
                  <th className="text-center font-sans font-normal pb-1">Bigs</th>
                </tr>
              </thead>
              <tbody className="text-illini-orange text-center">
                {POSITION_FIT_ROWS.map((row) => (
                  <tr key={row.skill}>
                    <td className="text-left text-gray-400 py-0.5">{SKILL_LABELS[row.skill]}</td>
                    <td>{row.g}</td>
                    <td>{row.f}</td>
                    <td>{row.c}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-500 mt-2">
              These are fixed position-fit multipliers used by the model, not player-specific learned values. Position
              groups come from the player&apos;s listed position: G = guards, F = wings/forwards, and C = bigs/centers.
            </p>
            <p>
              <strong className="text-gray-300">When nothing is actionable:</strong> Usually every skill fails at
              least one gate — opportunity near 0, team need below threshold, zero projected value, or poor position
              fit. The UI still shows a top skill for context with the limited-gap badge rather than implying a firm
              staff mandate.
            </p>
          </DetailBox>
        </div>
      </MethodologyAccordion>

      <MethodologyAccordion
        title="Projected Value on the Dev Board Tab"
        id="projected-value-dev-board"
      >
        <p className="text-gray-200 font-medium leading-relaxed mb-3">
          {DEV_BOARD_PROJ_VALUE_HEADLINE}
        </p>
        <p>
          Projected Value estimates the rough season value of improving a skill by a realistic amount. It is shown in
          points/possession value terms so users can compare the possible size of different development gains.
        </p>
        <p>{REALISTIC_TARGET_CALIBRATION}</p>
        <p>
          Projected Value is not part of the DPS weights. DPS decides which skill is the best development priority;
          Projected Value estimates the possible size of the improvement if that skill improves.
        </p>
        <p>
          On the Dev Board, Projected Value is shown once per player for the selected Top Priority skill only. It does
          not show projected value for all nine skills on the Dev Board.
        </p>
        <p className="text-gray-300 text-sm font-semibold mt-4 mb-2">Basic examples</p>
        <ul className="list-disc pl-5 space-y-1 text-gray-400">
          {SKILL_ORDER.map((key) => (
            <li key={key}>
              <strong className="text-gray-300">{SKILL_LABELS[key]}:</strong>{' '}
              {PROJ_VALUE_EXAMPLE_BY_SKILL[key]}
            </li>
          ))}
        </ul>

        <div className="border-t border-surface-border pt-4 mt-4">
          <h4 className="font-semibold text-white mb-2">Realistic Targets</h4>
          <p className="text-gray-400">
            The table below lists the base realistic increment and ceiling or floor applied to each skill.
          </p>
          <DetailBox>
            <p className="font-mono text-xs text-illini-orange">
              Higher-is-better stats: Target = min(current + suggested improvement, ceiling)
            </p>
            <p className="font-mono text-xs text-illini-orange">
              Lower-is-better stats: Target = max(current × (1 − suggested reduction), floor)
            </p>
            <p className="text-sm text-gray-400 leading-relaxed">
              The increment is the realistic one-season improvement amount. The ceiling prevents a player from being
              projected beyond a reasonable high-end benchmark. For turnovers and fouls, the model uses a floor because
              lower is better.
            </p>
          </DetailBox>
          <table className="w-full text-xs mt-3">
            <thead>
              <tr className="text-gray-500 border-b border-surface-border">
                <th className="text-left font-semibold pb-2 pr-3">Skill</th>
                <th className="text-left font-semibold pb-2 pr-3">Base realistic increment</th>
                <th className="text-left font-semibold pb-2">Ceiling / floor idea</th>
              </tr>
            </thead>
            <tbody className="text-gray-400 leading-relaxed">
              {SKILL_ORDER.map((key, i) => {
                const row = REALISTIC_TARGET_BY_SKILL[key];
                const border =
                  i < SKILL_ORDER.length - 1 ? 'border-b border-surface-border/50' : '';
                return (
                  <tr key={key} className={border}>
                    <td className="py-2 pr-3">{SKILL_LABELS[key]}</td>
                    <td className="py-2 pr-3 text-illini-orange">{row.increment}</td>
                    <td className="py-2">{row.ceiling}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </MethodologyAccordion>

      <MethodologyAccordion
        title="Improvement Simulator"
        id="improvement-simulator"
        hashTargets={['load-recommended-improvement-scenario']}
      >
        <div className="space-y-4">
          <div id="load-recommended-improvement-scenario" className="scroll-mt-24">
            <h4 className="font-semibold text-white mb-2">{RECOMMENDED_SCENARIO_LABEL}</h4>
            <p className="text-gray-400 leading-relaxed">
              This button fills the sliders for each skill using the formula below for the selected player.
            </p>
            <DetailBox>
              <p className="font-mono text-xs text-illini-orange leading-relaxed">
                Suggested Improvement = Base Realistic Increment × DPS Priority Factor × Opportunity Factor
              </p>
            </DetailBox>

            <div className="mt-4 space-y-4 text-gray-400 text-sm leading-relaxed">
              <div>
                <h5 className="font-semibold text-white mb-1">1. Base Realistic Increment</h5>
                <p>
                  The Base Realistic Increment is the starting one-season improvement amount for each skill. It comes
                  from the historical calibration table above. For example, {SKILL_LABELS.shooting} starts at +5
                  percentage points, {SKILL_LABELS.free_throw} starts at +8 percentage points, and{' '}
                  {SKILL_LABELS.ball_security} starts at a 12%
                  turnover reduction.
                </p>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">2. DPS Priority Factor</h5>
                <p>
                  The DPS Priority Factor scales the improvement based on where that skill ranks for the player by
                  adjusted DPS. A player&apos;s Top Priority skill receives the largest share of the realistic increment.
                  Skills ranked lower receive smaller suggested changes because they are less central to the
                  player&apos;s development profile.
                </p>
                <table className="w-full text-xs mt-2">
                  <thead>
                    <tr className="text-gray-500 border-b border-surface-border">
                      <th className="text-left font-semibold pb-1 pr-3">Rank by adjusted DPS</th>
                      <th className="text-left font-semibold pb-1">Priority factor</th>
                    </tr>
                  </thead>
                  <tbody className="text-illini-orange">
                    <tr className="border-b border-surface-border/50">
                      <td className="py-1 pr-3 text-gray-400">1st</td>
                      <td className="py-1">1.00</td>
                    </tr>
                    <tr className="border-b border-surface-border/50">
                      <td className="py-1 pr-3 text-gray-400">2nd–3rd</td>
                      <td className="py-1">0.70</td>
                    </tr>
                    <tr className="border-b border-surface-border/50">
                      <td className="py-1 pr-3 text-gray-400">4th–6th</td>
                      <td className="py-1">0.35</td>
                    </tr>
                    <tr>
                      <td className="py-1 pr-3 text-gray-400">7th–9th</td>
                      <td className="py-1">0.15</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div>
                <h5 className="font-semibold text-white mb-1">3. Opportunity Factor</h5>
                <p>
                  The Opportunity Factor scales the improvement based on whether the player actually has room to improve
                  in that skill. A skill with little or no Player Improvement Opportunity receives a small or zero
                  suggested change, even if it has theoretical projected value.
                </p>
                <table className="w-full text-xs mt-2">
                  <thead>
                    <tr className="text-gray-500 border-b border-surface-border">
                      <th className="text-left font-semibold pb-1 pr-3">Player Opportunity</th>
                      <th className="text-left font-semibold pb-1">Opportunity factor</th>
                    </tr>
                  </thead>
                  <tbody className="text-illini-orange">
                    <tr className="border-b border-surface-border/50">
                      <td className="py-1 pr-3 text-gray-400">&lt; 10</td>
                      <td className="py-1">0.00</td>
                    </tr>
                    <tr className="border-b border-surface-border/50">
                      <td className="py-1 pr-3 text-gray-400">10–20</td>
                      <td className="py-1">0.25</td>
                    </tr>
                    <tr className="border-b border-surface-border/50">
                      <td className="py-1 pr-3 text-gray-400">20–40</td>
                      <td className="py-1">0.60</td>
                    </tr>
                    <tr>
                      <td className="py-1 pr-3 text-gray-400">40+</td>
                      <td className="py-1">1.00</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <p>
                After these factors are applied, the target is capped by the ceiling or floor from the Realistic
                Targets table.
              </p>
              <p className="text-gray-500">
                <strong className="text-gray-400">Example:</strong> If {SKILL_LABELS.shooting} is a player&apos;s
                2nd-ranked skill and his shooting opportunity score is 35, the suggested improvement for{' '}
                {SKILL_LABELS.shooting} is +5.0 × 0.70 ×
                0.60 = +2.1 percentage points, before applying the 3P% ceiling.
              </p>
            </div>
          </div>

          <div className="border-t border-surface-border pt-4">
            <h4 className="font-semibold text-white mb-2">Calculated Projected Value (Manual Simulator)</h4>
            <p>
              Manual sliders are user-controlled what-if scenarios. They do not have to match the model&apos;s
              recommended scenario. Moving a slider higher tests a more aggressive assumption; moving it lower tests a
              smaller improvement.
            </p>
          </div>

          <div className="border-t border-surface-border pt-4">
            <h4 className="font-semibold text-white mb-2">
              Why Top Development Priority and Highest Raw Point Upside Can Differ
            </h4>
            <p>
              Top Priority is based on adjusted DPS and actionability. Highest Raw Point Upside is based on the point
              estimate from the current slider scenario. These can differ because high-volume scoring skills can create
              more raw projected points, while ball security, playmaking, defense, or rebounding may still be the
              better development priority.
            </p>
          </div>

          <p className="text-xs text-gray-500 border-t border-surface-border pt-4">
            Detailed calibration choices, exact slider tier rules, opportunity gating, and edge-case handling are
            documented in the technical write-up.
          </p>
        </div>
      </MethodologyAccordion>

      <MethodologyAccordion title="Development Leverage Score" id="development-leverage-score">
        <p>
          <strong className="text-white">Whole-player score</strong> — not per skill. Answers: &quot;Who on this
          roster is the best bet to invest development time in?&quot;
        </p>
        <p className="font-mono text-xs text-illini-orange bg-surface/80 rounded px-3 py-2">
          Leverage = 0.30×Production + 0.30×Upside + 0.20×Need match + 0.10×Minutes + 0.10×Class runway
        </p>
        <LeverageWeightChart />
        <ul className="list-disc pl-5 space-y-3">
          <li>
            <strong className="text-white">Production (30%)</strong> — Normalized 0–100 across the rotation pool.
            <DetailBox>
              <p className="text-sm text-gray-400 mb-2">
                <strong className="text-gray-300">Current release</strong> — full-pool advanced ingest is available,
                so every player uses the same advanced production blend:
              </p>
              <p className="font-mono text-xs text-illini-orange">
                30% BPM + 20% TS% + 15% usage + 15% PPG + 10% PER (Player Efficiency Rating) + 10% WS/40 (or Win Shares)
              </p>
              <p className="font-mono text-xs text-illini-orange">
                Production = min-max normalize Raw across all rotation players → 0–100
              </p>
            </DetailBox>
          </li>
          <li>
            <strong className="text-white">Upside (30%)</strong> — Average DPS of the player&apos;s top three
            skill priorities.
          </li>
          <li>
            <strong className="text-white">Need match (20%)</strong> — Average team need on those top three
            skills.
          </li>
          <li>
            <strong className="text-white">Minutes (10%)</strong> — MPG ÷ 35 × 100 (capped at 100).
          </li>
          <li>
            <strong className="text-white">Class-year runway (10%)</strong> — Fr 85, So 80, Jr 70, Sr 55, Gr
            50.
            <DetailBox>
              <p className="text-sm text-gray-400">
                Class-year runway is a small 10% component and uses projected 2026–27 class labels when available.
                The model does not attempt to predict early NBA Draft decisions, transfer decisions, or future
                roster movement unless a player is already confirmed departed. This keeps the score transparent
                and avoids guessing. The other 90% of Development Leverage comes from production, upside, team
                need match, and minutes.
              </p>
            </DetailBox>
          </li>
        </ul>
      </MethodologyAccordion>

      <MethodologyAccordion title="Why Useful to GM / Coaching Staff">
        <div className="space-y-4 text-gray-400">
          <p>
            DevelopmentIQ is designed to help a college basketball program connect player development decisions
            to team-level needs. Instead of identifying weaknesses in isolation, the app asks whether improving
            a specific skill would actually create value for that player&apos;s current roster context.
          </p>

          <div>
            <h4 className="font-semibold text-white mb-2">For Coaching Staff</h4>
            <p>
              Coaches have limited practice time, individual workout time, and film-session bandwidth.
              DevelopmentIQ helps prioritize which skills deserve the most attention for each rotation player
              by combining individual improvement opportunity, team need, minutes leverage, improvement
              realism, and basketball impact.
            </p>
            <p className="mt-2">This can support:</p>
            <ul className="list-disc pl-5 space-y-1 mt-2">
              <li>Individual development plans</li>
              <li>Offseason workout priorities</li>
              <li>Practice planning</li>
              <li>Role conversations with players</li>
              <li>Film-session focus areas</li>
              <li>Identifying which improvements would most affect team performance</li>
            </ul>
            <p className="mt-3">
              For example, if a team struggles on the defensive glass, the app can surface which rotation
              players have the clearest defensive rebounding development path. If a team lacks spacing, it can
              identify which players&apos; shooting improvement would create the most lineup value.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-2">
              For General Managers / Basketball Operations
            </h4>
            <p>
              From a roster-construction perspective, DevelopmentIQ separates what the team lacks (Team Need
              by skill on the Needs Map) from who on the roster can realistically improve (DPS and Top
              Priority per player). Development Leverage is a whole-player rank only — there is no leverage
              score by skill. If team need is high in an area and several rotation players have actionable
              focus in that skill, internal development may be enough. If need is severe but no rotation player
              has actionable DPS there, the gap may require portal, recruiting, or lineup-construction.
            </p>
            <p className="mt-2">This can support:</p>
            <ul className="list-disc pl-5 space-y-1 mt-2">
              <li>Roster weakness visibility</li>
              <li>Internal upside evaluation</li>
              <li>Portal and offseason planning</li>
              <li>Identifying players whose growth could change the team&apos;s ceiling</li>
              <li>Deciding which team needs can be solved internally versus externally</li>
              <li>Evaluating whether roster construction aligns with the program&apos;s desired playing style</li>
            </ul>
          </div>

          <p className="text-gray-500 border-t border-surface-border pt-4">
            The goal is not to replace coaching judgment. The tool is meant to give staff a transparent,
            data-supported starting point for development conversations and roster planning.
          </p>
        </div>
      </MethodologyAccordion>

      <MethodologyAccordion title="Limitations">
        <p>
          DevelopmentIQ is a decision-support tool, not a complete player evaluation system. Public box-score
          and efficiency data cannot fully capture defensive assignments, scheme responsibilities, shot quality,
          player health, practice performance, or film context. A player&apos;s true development value also
          depends on role, lineup combinations, coaching priorities, and how opponents guard him.
        </p>
        <p className="mt-3">
          The improvement estimates are transparent heuristics, not guarantees. Player development is nonlinear,
          and a realistic improvement in one skill may not translate cleanly into game impact without changes in
          role, usage, or lineup fit. The app is meant to supplement coaching judgment by organizing the data,
          not replace staff evaluation.
        </p>
      </MethodologyAccordion>

      <MethodologyAccordion title="Future Improvements">
        <p>
          Future versions could add live data ingestion, multi-season development curves, and lineup on/off
          context so player priorities reflect how different combinations actually perform together.
          Shot-quality data and play-type indicators would also improve the model by separating &quot;bad
          results&quot; from &quot;bad process.&quot;
        </p>
        <p className="mt-3">
          The tool could also integrate practice-tracking data, film tags, and staff-adjustable weights. That
          would let a program customize DevelopmentIQ to its own offensive system, defensive scheme, and
          player-development philosophy instead of relying only on public statistical proxies.
        </p>
      </MethodologyAccordion>
    </div>
  );
}
