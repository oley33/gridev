"use client";

import { useEffect, useState } from "react";
import {
  getBacktest,
  getConsensusSnapshot,
  type BacktestMetrics,
  type BacktestResult,
  type ConsensusRow,
  type ConsensusSnapshot,
} from "../lib/api";
import PositionBadge from "../components/position-badge";

const POSITIONS = ["QB", "RB", "WR", "TE"] as const;
const FORECASTERS = [
  { key: "model", label: "Our Model", color: "text-accent" },
  { key: "naive", label: "Naive (Prior PPG)", color: "text-muted" },
  {
    key: "weighted_history",
    label: "Weighted History",
    color: "text-muted",
  },
] as const;

function MetricCell({
  value,
  highlight,
  digits = 2,
}: {
  value: number;
  highlight?: boolean;
  digits?: number;
}) {
  return (
    <span
      className={`font-mono ${
        highlight ? "text-accent font-semibold" : "text-foreground"
      }`}
    >
      {value.toFixed(digits)}
    </span>
  );
}

function bestForMetric(
  metrics: Record<string, BacktestMetrics>,
  metric: keyof BacktestMetrics,
  higherIsBetter: boolean
): string {
  const entries = Object.entries(metrics);
  if (entries.length === 0) return "";
  let bestKey = entries[0][0];
  let bestVal = entries[0][1][metric] as number;
  for (const [k, m] of entries) {
    const v = m[metric] as number;
    if (higherIsBetter ? v > bestVal : v < bestVal) {
      bestKey = k;
      bestVal = v;
    }
  }
  return bestKey;
}

function SummaryTable({
  metrics,
}: {
  metrics: Record<string, BacktestMetrics>;
}) {
  const bestMae = bestForMetric(metrics, "mae", false);
  const bestRmse = bestForMetric(metrics, "rmse", false);
  const bestR2 = bestForMetric(metrics, "r2", true);
  const bestRho = bestForMetric(metrics, "spearman", true);

  return (
    <div className="overflow-x-auto rounded-lg border border-card-border">
      <table className="w-full text-sm">
        <thead className="bg-card">
          <tr className="border-b border-card-border">
            <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
              Forecaster
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              MAE ↓
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              RMSE ↓
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              R² ↑
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              Spearman ρ ↑
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              n
            </th>
          </tr>
        </thead>
        <tbody>
          {FORECASTERS.map(({ key, label, color }) => {
            const m = metrics[key];
            if (!m) return null;
            return (
              <tr
                key={key}
                className="border-b border-card-border/50 last:border-0"
              >
                <td className={`px-3 py-2 font-medium ${color}`}>{label}</td>
                <td className="px-3 py-2 text-right">
                  <MetricCell value={m.mae} highlight={bestMae === key} />
                </td>
                <td className="px-3 py-2 text-right">
                  <MetricCell value={m.rmse} highlight={bestRmse === key} />
                </td>
                <td className="px-3 py-2 text-right">
                  <MetricCell
                    value={m.r2}
                    highlight={bestR2 === key}
                    digits={3}
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  <MetricCell
                    value={m.spearman}
                    highlight={bestRho === key}
                    digits={3}
                  />
                </td>
                <td className="px-3 py-2 text-right font-mono text-muted">
                  {m.n}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PerYearMAETable({ backtest }: { backtest: BacktestResult }) {
  const rows = backtest.per_year;
  const years = backtest.target_years;

  return (
    <div className="overflow-x-auto rounded-lg border border-card-border">
      <table className="w-full text-sm">
        <thead className="bg-card">
          <tr className="border-b border-card-border">
            <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
              Pos
            </th>
            <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
              Year
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-accent">
              Model MAE
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              Naive MAE
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              WHist MAE
            </th>
            <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
              Best
            </th>
          </tr>
        </thead>
        <tbody>
          {POSITIONS.flatMap((pos) =>
            years
              .map((yr) => rows.find((r) => r.position === pos && r.target_year === yr))
              .filter((r): r is BacktestResult["per_year"][number] => r != null)
              .map((r, i) => {
                const vals = {
                  model: r.model.mae,
                  naive: r.naive.mae,
                  weighted_history: r.weighted_history.mae,
                };
                const best = Object.entries(vals).sort((a, b) => a[1] - b[1])[0][0];
                const labels: Record<string, string> = {
                  model: "Model",
                  naive: "Naive",
                  weighted_history: "WHist",
                };
                return (
                  <tr
                    key={`${pos}-${r.target_year}`}
                    className={`border-b border-card-border/50 ${
                      i % 2 === 0 ? "bg-background" : "bg-card/30"
                    }`}
                  >
                    <td className="px-3 py-2">
                      <PositionBadge position={pos} />
                    </td>
                    <td className="px-3 py-2 font-mono text-muted">
                      {r.target_year}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MetricCell value={r.model.mae} highlight={best === "model"} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MetricCell value={r.naive.mae} highlight={best === "naive"} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <MetricCell
                        value={r.weighted_history.mae}
                        highlight={best === "weighted_history"}
                      />
                    </td>
                    <td className="px-3 py-2 text-right text-xs text-muted">
                      {labels[best]}
                    </td>
                  </tr>
                );
              })
          )}
        </tbody>
      </table>
    </div>
  );
}

function ConsensusRowList({ rows }: { rows: ConsensusRow[] }) {
  return (
    <div className="rounded-lg border border-card-border overflow-hidden">
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={r.player_id}
              className={`border-b border-card-border/50 last:border-0 ${
                i % 2 === 0 ? "bg-background" : "bg-card/30"
              }`}
            >
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <PositionBadge position={r.position} />
                  <span className="font-medium">{r.player_name}</span>
                  <span className="text-xs text-muted">{r.team}</span>
                </div>
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs text-muted whitespace-nowrap">
                us #{r.our_rank} &middot; FP #{r.fp_rank}
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs whitespace-nowrap">
                <span
                  className={
                    r.rank_diff > 0 ? "text-success" : "text-danger"
                  }
                >
                  {r.rank_diff > 0 ? "+" : ""}
                  {r.rank_diff}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PerformancePage() {
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [consensus, setConsensus] = useState<ConsensusSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getBacktest(), getConsensusSnapshot()])
      .then(([bt, cs]) => {
        setBacktest(bt);
        setConsensus(cs);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-6">
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-danger">
          Failed to load performance data. Is the API running on localhost:8000?
          <div className="mt-1 text-sm opacity-75">{error}</div>
        </div>
      </div>
    );
  }

  if (loading || !backtest || !consensus) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  const [firstYear, lastYear] = [
    backtest.target_years[0],
    backtest.target_years[backtest.target_years.length - 1],
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Model Performance</h1>
        <p className="mt-1 text-sm text-muted">
          Walk-forward backtest of our model against naive baselines, plus a
          current-year comparison against FantasyPros consensus.
        </p>
      </div>

      {/* --- Overall backtest --- */}
      <section className="mb-10">
        <h2 className="mb-2 text-lg font-semibold">
          Overall Backtest ({firstYear}–{lastYear})
        </h2>
        <p className="mb-4 text-sm text-muted">
          Walk-forward validation: for each target season, we train only on
          data from prior seasons, then predict PPG for every player and
          compare against what they actually posted. Lower MAE/RMSE is better;
          higher R² and Spearman ρ are better.
        </p>
        <SummaryTable metrics={backtest.overall} />
      </section>

      {/* --- Per-position backtest --- */}
      <section className="mb-10">
        <h2 className="mb-2 text-lg font-semibold">By Position</h2>
        <p className="mb-4 text-sm text-muted">
          Each position is modeled separately with its own hyperparameters.
          QB is the hardest position for the naive baseline (high year-over-year
          variance), which is where our model gains the most.
        </p>
        <div className="grid gap-6 md:grid-cols-2">
          {POSITIONS.map((pos) => {
            const metrics = backtest.per_position[pos];
            if (!metrics) return null;
            return (
              <div key={pos}>
                <div className="mb-2 flex items-center gap-2">
                  <PositionBadge position={pos} />
                  <span className="text-sm font-medium">{pos} — 5 yr aggregate</span>
                </div>
                <SummaryTable metrics={metrics} />
              </div>
            );
          })}
        </div>
      </section>

      {/* --- Per-year MAE breakdown --- */}
      <section className="mb-10">
        <h2 className="mb-2 text-lg font-semibold">Year-by-Year MAE</h2>
        <p className="mb-4 text-sm text-muted">
          Full breakdown per position per target year. Highlighted cell marks
          the lowest MAE among the three forecasters.
        </p>
        <PerYearMAETable backtest={backtest} />
      </section>

      {/* --- Consensus snapshot --- */}
      <section className="mb-10">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h2 className="text-lg font-semibold">
            vs FantasyPros Consensus ({consensus.season})
          </h2>
          <span className="text-xs text-muted">
            Scraped {consensus.scrape_date}
          </span>
        </div>
        <p className="mb-4 text-sm text-muted">
          FantasyPros ECR historical snapshots aren&apos;t available through
          nflreadpy, so we can&apos;t backtest against consensus. Instead this
          is a point-in-time comparison: how our current {consensus.season}{" "}
          rankings line up with the current FP ECR.
        </p>

        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
          <div className="rounded-lg border border-card-border bg-card p-4">
            <div className="text-xs uppercase tracking-wider text-muted">
              Overall Spearman ρ
            </div>
            <div className="mt-1 text-2xl font-mono font-bold">
              {consensus.overall_spearman.toFixed(3)}
            </div>
            <div className="mt-1 text-xs text-muted">
              cross-position (conflated by positional scarcity)
            </div>
          </div>
          <div className="rounded-lg border border-card-border bg-card p-4">
            <div className="text-xs uppercase tracking-wider text-muted">
              Top-100 Spearman ρ
            </div>
            <div className="mt-1 text-2xl font-mono font-bold">
              {consensus.top_100_spearman.toFixed(3)}
            </div>
            <div className="mt-1 text-xs text-muted">elite tier only</div>
          </div>
          <div className="rounded-lg border border-card-border bg-card p-4">
            <div className="text-xs uppercase tracking-wider text-muted">
              Matched Players
            </div>
            <div className="mt-1 text-2xl font-mono font-bold">
              {consensus.n_matched}
            </div>
            <div className="mt-1 text-xs text-muted">
              by name + position
            </div>
          </div>
          <div className="rounded-lg border border-card-border bg-card p-4">
            <div className="text-xs uppercase tracking-wider text-muted">
              Best per-pos agreement
            </div>
            <div className="mt-1 text-2xl font-mono font-bold">
              {Math.max(
                ...Object.values(consensus.per_position).map((p) => p.spearman)
              ).toFixed(3)}
            </div>
            <div className="mt-1 text-xs text-muted">
              {
                Object.entries(consensus.per_position).sort(
                  (a, b) => b[1].spearman - a[1].spearman
                )[0][0]
              }
            </div>
          </div>
        </div>

        <div className="mb-6 rounded-lg border border-card-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-card">
              <tr className="border-b border-card-border">
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
                  Position
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                  Spearman ρ
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                  Mean |rank diff|
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                  n
                </th>
              </tr>
            </thead>
            <tbody>
              {POSITIONS.map((pos) => {
                const p = consensus.per_position[pos];
                if (!p) return null;
                return (
                  <tr
                    key={pos}
                    className="border-b border-card-border/50 last:border-0"
                  >
                    <td className="px-3 py-2">
                      <PositionBadge position={pos} />
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {p.spearman.toFixed(3)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {p.mean_abs_rank_diff.toFixed(1)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-muted">
                      {p.n_matched}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-semibold text-success">
              We rank higher than consensus
            </h3>
            <p className="mb-2 text-xs text-muted">
              Players we project above where the public market is drafting them.
            </p>
            <ConsensusRowList rows={consensus.we_rank_higher.slice(0, 10)} />
          </div>
          <div>
            <h3 className="mb-2 text-sm font-semibold text-danger">
              We rank lower than consensus
            </h3>
            <p className="mb-2 text-xs text-muted">
              Players the market is higher on than our model — potential fades.
            </p>
            <ConsensusRowList rows={consensus.we_rank_lower.slice(0, 10)} />
          </div>
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-2 text-lg font-semibold">Methodology</h2>
        <div className="rounded-lg border border-card-border bg-card p-4 text-sm text-muted space-y-2">
          <p>
            <span className="font-semibold text-foreground">Walk-forward validation</span>
            {": "}
            for each target year Y, we train only on data strictly prior to Y,
            then predict every player&apos;s next-season PPG. No future leakage.
          </p>
          <p>
            <span className="font-semibold text-foreground">Forecasters compared</span>:{" "}
            <span className="text-accent">Our Model</span> (position-specific
            XGBoost + Bayesian blending with historical priors),{" "}
            <span>Naive</span> (predict next year = most recent season&apos;s PPG), and{" "}
            <span>Weighted History</span> (exponentially-weighted 3-year average
            regressed toward the position mean).
          </p>
          <p>
            <span className="font-semibold text-foreground">Metrics</span>: MAE
            (mean absolute error in PPG), RMSE (penalizes outliers more), R²
            (variance explained), and Spearman ρ (rank correlation — how well
            we order players from best to worst).
          </p>
        </div>
      </section>
    </div>
  );
}
