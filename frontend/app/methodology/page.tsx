import Link from "next/link";

// ---------------------------------------------------------------------------
// Reusable pieces
// ---------------------------------------------------------------------------

function Section({
  id,
  eyebrow,
  title,
  description,
  children,
}: {
  id?: string;
  eyebrow?: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="mb-16 scroll-mt-20">
      <div className="mb-6">
        {eyebrow && (
          <div className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
            {eyebrow}
          </div>
        )}
        <h2 className="text-2xl font-bold">{title}</h2>
        {description && (
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">
            {description}
          </p>
        )}
      </div>
      {children}
    </section>
  );
}

function Card({
  title,
  subtitle,
  children,
  accent = "border-card-border",
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className={`rounded-xl border bg-card p-5 ${accent}`}>
      {title && (
        <div className="mb-2">
          <div className="font-semibold">{title}</div>
          {subtitle && (
            <div className="text-xs text-muted mt-0.5">{subtitle}</div>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

function Stat({
  value,
  label,
  hint,
}: {
  value: string;
  label: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-card-border bg-card p-5">
      <div className="font-mono text-3xl font-bold text-accent">{value}</div>
      <div className="mt-1 text-sm font-medium">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  );
}

function Code({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-card-border bg-background p-4 text-xs leading-relaxed">
      <code className="font-mono text-foreground">{children}</code>
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Diagram 1: Pipeline flow
// ---------------------------------------------------------------------------

function PipelineDiagram() {
  const stages = [
    {
      label: "Raw Data",
      sub: "nflreadpy\n2012–2025",
      color: "#64748b",
    },
    {
      label: "Feature Matrix",
      sub: "42 features\n6,650 player-seasons",
      color: "#3b82f6",
    },
    {
      label: "XGBoost",
      sub: "per position\nwalk-forward",
      color: "#22c55e",
    },
    {
      label: "Bayesian Update",
      sub: "priors +\ncalibration",
      color: "#a855f7",
    },
    {
      label: "Monte Carlo",
      sub: "10k sims\nskew-normal",
      color: "#f59e0b",
    },
    {
      label: "VOR + API",
      sub: "FastAPI →\nNext.js UI",
      color: "#ef4444",
    },
  ];

  const boxW = 140;
  const boxH = 78;
  const gap = 36;
  const width = stages.length * (boxW + gap) - gap;
  const height = boxH + 40;

  return (
    <div className="overflow-x-auto rounded-xl border border-card-border bg-card p-6">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="mx-auto block w-full max-w-5xl"
        role="img"
        aria-label="Data pipeline flow"
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
          </marker>
        </defs>

        {stages.map((s, i) => {
          const x = i * (boxW + gap);
          const y = 20;
          return (
            <g key={s.label}>
              <rect
                x={x}
                y={y}
                width={boxW}
                height={boxH}
                rx={10}
                fill="#0f172a"
                stroke={s.color}
                strokeWidth={2}
              />
              <text
                x={x + boxW / 2}
                y={y + 28}
                textAnchor="middle"
                className="font-semibold"
                fill="#e2e8f0"
                fontSize="14"
              >
                {s.label}
              </text>
              {s.sub.split("\n").map((line, j) => (
                <text
                  key={j}
                  x={x + boxW / 2}
                  y={y + 46 + j * 14}
                  textAnchor="middle"
                  fill="#94a3b8"
                  fontSize="11"
                  className="font-mono"
                >
                  {line}
                </text>
              ))}
              {i < stages.length - 1 && (
                <line
                  x1={x + boxW + 4}
                  y1={y + boxH / 2}
                  x2={x + boxW + gap - 4}
                  y2={y + boxH / 2}
                  stroke="#64748b"
                  strokeWidth={1.5}
                  markerEnd="url(#arrow)"
                />
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diagram 2: Walk-forward timeline
// ---------------------------------------------------------------------------

function WalkForwardDiagram() {
  const years = [2019, 2020, 2021, 2022, 2023, 2024, 2025];
  const firstYear = 2013;
  const allYears = [] as number[];
  for (let y = firstYear; y <= 2025; y++) allYears.push(y);

  return (
    <div className="rounded-xl border border-card-border bg-card p-6">
      <div className="mb-4 flex flex-wrap items-center gap-4 text-xs text-muted">
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-6 rounded bg-accent/70" />
          Train
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-6 rounded bg-success/70" />
          Test (predict this season)
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-block h-3 w-6 rounded bg-card-border" />
          Not yet used
        </div>
      </div>

      <div className="space-y-1.5">
        {years.map((targetYear) => {
          const featureYear = targetYear - 1;
          return (
            <div key={targetYear} className="flex items-center gap-3">
              <div className="w-24 shrink-0 text-right text-xs font-mono text-muted">
                target {targetYear}
              </div>
              <div className="grid flex-1 gap-0.5" style={{ gridTemplateColumns: `repeat(${allYears.length}, minmax(0, 1fr))` }}>
                {allYears.map((yr) => {
                  let cls = "bg-card-border/50";
                  if (yr < featureYear) cls = "bg-accent/70";
                  else if (yr === featureYear) cls = "bg-success/70";
                  return (
                    <div
                      key={yr}
                      className={`h-5 rounded-sm ${cls}`}
                      title={`${yr}`}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}

        {/* x-axis */}
        <div className="flex items-center gap-3 pt-2">
          <div className="w-24 shrink-0" />
          <div className="grid flex-1 gap-0.5" style={{ gridTemplateColumns: `repeat(${allYears.length}, minmax(0, 1fr))` }}>
            {allYears.map((yr) => (
              <div
                key={yr}
                className="text-[9px] font-mono text-muted text-center"
              >
                {yr % 2 === 0 ? yr : ""}
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-4 text-xs text-muted max-w-2xl">
        For every target season in the backtest, the model only sees data from
        strictly earlier seasons. This prevents future-data leakage and matches
        how the model would be used in production — trained on the past,
        predicting the unknown next year.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diagram 3: Skew-normal distribution with floor / median / ceiling markers
// ---------------------------------------------------------------------------

function DistributionDiagram() {
  // Hand-shaped curve: rising from zero, peak around median, long right tail.
  const points: [number, number][] = [];
  const width = 600;
  const height = 220;
  const mu = 260;
  const sigma = 75;
  const alpha = 2; // skew
  // Skew-normal PDF (un-normalized)
  const pdf = (x: number) => {
    const z = (x - mu) / sigma;
    const phi = Math.exp(-0.5 * z * z);
    // approximation of 2 * phi(z) * Phi(alpha * z)
    const cdfApprox = 0.5 * (1 + Math.tanh((alpha * z) * 0.7978));
    return phi * cdfApprox;
  };
  let maxY = 0;
  for (let x = 40; x <= width - 20; x += 2) {
    const y = pdf(x);
    if (y > maxY) maxY = y;
    points.push([x, y]);
  }
  const scaleY = (height - 60) / maxY;
  const path =
    points
      .map(
        ([x, y], i) =>
          `${i === 0 ? "M" : "L"}${x},${height - 30 - y * scaleY}`
      )
      .join(" ") + ` L${points[points.length - 1][0]},${height - 30} L${points[0][0]},${height - 30} Z`;

  // approximate percentile positions on this hand-drawn curve
  const p10 = 180;
  const p50 = 275;
  const p90 = 410;

  const axisY = height - 30;

  return (
    <div className="rounded-xl border border-card-border bg-card p-6">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="mx-auto block w-full max-w-3xl"
        role="img"
        aria-label="Monte Carlo outcome distribution"
      >
        <defs>
          <linearGradient id="distFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {/* axis */}
        <line
          x1="30"
          y1={axisY}
          x2={width - 10}
          y2={axisY}
          stroke="#334155"
          strokeWidth={1}
        />
        {/* curve */}
        <path d={path} fill="url(#distFill)" stroke="#3b82f6" strokeWidth={2} />

        {/* markers */}
        {[
          { x: p10, label: "P10 · Floor", color: "#ef4444" },
          { x: p50, label: "P50 · Median", color: "#3b82f6" },
          { x: p90, label: "P90 · Ceiling", color: "#22c55e" },
        ].map((m) => (
          <g key={m.label}>
            <line
              x1={m.x}
              y1={axisY}
              x2={m.x}
              y2={axisY - (height - 80)}
              stroke={m.color}
              strokeWidth={1.5}
              strokeDasharray="4 4"
            />
            <rect
              x={m.x - 42}
              y={10}
              width={84}
              height={20}
              rx={4}
              fill={m.color}
              fillOpacity="0.15"
              stroke={m.color}
              strokeWidth={1}
            />
            <text
              x={m.x}
              y={24}
              textAnchor="middle"
              fontSize="11"
              fill={m.color}
              className="font-semibold"
            >
              {m.label}
            </text>
          </g>
        ))}

        {/* x-label */}
        <text
          x={width / 2}
          y={height - 8}
          textAnchor="middle"
          fontSize="11"
          fill="#94a3b8"
        >
          Simulated season PPG (10,000 samples)
        </text>
      </svg>

      <div className="mt-2 grid grid-cols-1 gap-3 text-xs text-muted sm:grid-cols-3">
        <div>
          <span className="font-semibold text-danger">P10 · Floor</span> —
          &ldquo;worst reasonable case&rdquo;. Beats this 90% of the time.
        </div>
        <div>
          <span className="font-semibold text-accent">P50 · Median</span> —
          expected outcome. What we call the projection.
        </div>
        <div>
          <span className="font-semibold text-success">P90 · Ceiling</span> —
          &ldquo;smash season&rdquo;. Drives boom probability.
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diagram 4: Bayesian blend
// ---------------------------------------------------------------------------

function BayesianBlendDiagram() {
  return (
    <div className="rounded-xl border border-card-border bg-card p-6">
      <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr_auto_1fr] items-center">
        <div className="rounded-lg border border-success/40 bg-success/5 p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-success">
            Likelihood
          </div>
          <div className="mt-1 text-sm font-semibold">XGBoost prediction</div>
          <div className="mt-2 font-mono text-xs text-muted">
            μ_model, σ_model
          </div>
          <div className="mt-3 text-xs text-muted">
            Sharp signal from 42 features — target share, efficiency, team
            context. σ is calibrated via 5-fold CV residuals.
          </div>
        </div>

        <div className="hidden md:block text-center text-2xl text-muted">+</div>

        <div className="rounded-lg border border-accent/40 bg-accent/5 p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-accent">
            Prior
          </div>
          <div className="mt-1 text-sm font-semibold">Player history</div>
          <div className="mt-2 font-mono text-xs text-muted">
            μ_prior, σ_prior, n_seasons
          </div>
          <div className="mt-3 text-xs text-muted">
            Career PPG mean + variance. Weighted by √n_seasons so stable
            veterans anchor more than one-season wonders.
          </div>
        </div>

        <div className="hidden md:block text-center text-2xl text-muted">=</div>

        <div className="rounded-lg border border-te/50 bg-te/5 p-4">
          <div className="text-xs font-semibold uppercase tracking-wider text-te">
            Posterior
          </div>
          <div className="mt-1 text-sm font-semibold">Calibrated estimate</div>
          <div className="mt-2 font-mono text-xs text-muted">
            μ_post, σ_post
          </div>
          <div className="mt-3 text-xs text-muted">
            85% weight on XGBoost (the better predictor), 15% nudge from prior.
            σ widened by a learned calibration factor so 80% intervals hit ~80%
            coverage.
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diagram 5: Feature taxonomy
// ---------------------------------------------------------------------------

function FeatureTaxonomy() {
  const groups = [
    {
      title: "Volume & Opportunity",
      color: "border-accent/40 bg-accent/5",
      desc: "What share of the pie does this player command?",
      items: [
        "target_share",
        "air_yards_share",
        "rush_share",
        "snap_pct",
        "redzone_target_share",
        "redzone_rush_share",
      ],
    },
    {
      title: "Efficiency",
      color: "border-success/40 bg-success/5",
      desc: "How much do they do with each opportunity?",
      items: [
        "yards_per_route_run",
        "yards_per_carry",
        "catch_rate",
        "catch_rate_over_expected",
        "true_catch_rate",
        "yards_after_catch",
      ],
    },
    {
      title: "Team Context",
      color: "border-te/40 bg-te/5",
      desc: "Who's around them and how good is the situation?",
      items: [
        "team_implied_total",
        "qb_cpoe",
        "offensive_line_rank",
        "pace_plays_per_game",
        "pass_rate_over_expected",
      ],
    },
    {
      title: "Regression Indicators",
      color: "border-rb/40 bg-rb/5",
      desc: "Luck vs skill — where's the mean reversion?",
      items: [
        "td_over_expected",
        "expected_td_rate",
        "fumble_rate",
        "deep_target_share",
      ],
    },
    {
      title: "Career Trajectory",
      color: "border-danger/40 bg-danger/5",
      desc: "Age, experience, and position-specific aging curves.",
      items: [
        "age",
        "years_experience",
        "position_age_curve_factor",
        "draft_capital",
        "career_games",
      ],
    },
    {
      title: "Historical Signal",
      color: "border-wr/40 bg-wr/5",
      desc: "Lagged features from prior seasons.",
      items: [
        "ppg_prev",
        "ppg_prev_2yr_avg",
        "games_prev",
        "role_consistency",
      ],
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {groups.map((g) => (
        <div
          key={g.title}
          className={`rounded-xl border p-4 ${g.color}`}
        >
          <div className="text-sm font-semibold">{g.title}</div>
          <div className="mt-1 text-xs text-muted">{g.desc}</div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {g.items.map((item) => (
              <code
                key={item}
                className="rounded bg-background/80 px-1.5 py-0.5 font-mono text-[11px] text-foreground"
              >
                {item}
              </code>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Diagram 6: Tech stack
// ---------------------------------------------------------------------------

function TechStack() {
  const layers = [
    {
      name: "Frontend",
      color: "border-wr/40 bg-wr/5",
      items: ["Next.js 16", "React 19", "Tailwind v4", "TypeScript"],
    },
    {
      name: "API",
      color: "border-success/40 bg-success/5",
      items: ["FastAPI", "Pydantic", "CORS + rate limit"],
    },
    {
      name: "ML",
      color: "border-te/40 bg-te/5",
      items: ["XGBoost", "SciPy", "scikit-learn", "NumPy / Pandas"],
    },
    {
      name: "Data",
      color: "border-accent/40 bg-accent/5",
      items: ["nflreadpy (polars)", "Parquet cache", "14 seasons · 2012-2025"],
    },
  ];
  return (
    <div className="flex flex-col gap-2">
      {layers.map((l) => (
        <div
          key={l.name}
          className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border px-4 py-3 ${l.color}`}
        >
          <div className="w-24 text-xs font-semibold uppercase tracking-wider">
            {l.name}
          </div>
          <div className="flex flex-wrap gap-2">
            {l.items.map((it) => (
              <span
                key={it}
                className="rounded bg-background/80 px-2 py-0.5 font-mono text-xs"
              >
                {it}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Hero */}
      <header className="mb-12">
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
          Methodology
        </div>
        <h1 className="mt-1 text-3xl font-bold sm:text-4xl">
          How the projections are built
        </h1>
        <p className="mt-4 max-w-3xl text-base leading-relaxed text-muted">
          An end-to-end ML pipeline that goes from raw NFL play-by-play to a
          calibrated projection with floor, ceiling, and boom/bust probability
          for every draftable player. Every modeling choice prioritizes two
          things: <span className="text-foreground">explainability</span>{" "}
          (we can answer &ldquo;why is this player ranked here?&rdquo;) and{" "}
          <span className="text-foreground">honest uncertainty</span> (the
          intervals we publish match the intervals we actually hit in backtests).
        </p>

        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat value="14" label="Seasons of data" hint="2012 – 2025" />
          <Stat value="6,650" label="Player-seasons" hint="training corpus" />
          <Stat value="42" label="Engineered features" hint="per player" />
          <Stat value="10,000" label="Monte Carlo sims" hint="per player" />
        </div>

        <nav className="mt-8 flex flex-wrap gap-2 text-xs">
          {[
            ["#pipeline", "1 · Pipeline"],
            ["#data", "2 · Data"],
            ["#features", "3 · Features"],
            ["#models", "4 · XGBoost"],
            ["#bayesian", "5 · Bayesian"],
            ["#montecarlo", "6 · Monte Carlo"],
            ["#vor", "7 · VOR"],
            ["#validation", "8 · Validation"],
            ["#stack", "9 · Stack"],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="rounded-full border border-card-border bg-card px-3 py-1.5 text-muted transition-colors hover:border-accent hover:text-accent"
            >
              {label}
            </a>
          ))}
        </nav>
      </header>

      {/* 1. Pipeline */}
      <Section
        id="pipeline"
        eyebrow="The system"
        title="End-to-end pipeline"
        description="Six stages turn raw nflverse data into draft-ready recommendations. Each layer has a single, well-defined responsibility — no 3,000-line notebooks."
      >
        <PipelineDiagram />
        <p className="mt-4 text-sm text-muted max-w-3xl">
          The stages are deliberately composable. You can train the XGBoost
          layer alone and evaluate it. You can swap out the Bayesian step for
          a quantile regression. You can run Monte Carlo against any point
          estimate. Each stage is an importable Python module with a clear
          contract.
        </p>
      </Section>

      {/* 2. Data */}
      <Section
        id="data"
        eyebrow="Data"
        title="14 seasons of NFL player data"
        description="Everything flows from nflreadpy — the actively-maintained successor to nfl_data_py (deprecated Sep 2025). Raw pulls are cached as Parquet so the pipeline is reproducible and fast."
      >
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Sources">
            <ul className="space-y-2 text-sm text-muted">
              <li>
                <span className="text-foreground">Play-by-play</span> — every
                offensive snap, used to derive target share, air yards,
                rush share, red-zone opportunity.
              </li>
              <li>
                <span className="text-foreground">Seasonal stats</span> —
                re-aggregated from weekly (rates averaged, counts summed)
                to avoid upstream inconsistencies.
              </li>
              <li>
                <span className="text-foreground">Rosters & draft picks</span>{" "}
                — age, experience, draft capital.
              </li>
              <li>
                <span className="text-foreground">Team & schedule</span> —
                implied totals, offensive line rank, schedule strength.
              </li>
            </ul>
          </Card>

          <Card title="Why re-aggregate?">
            <p className="text-sm text-muted leading-relaxed">
              Pre-computed seasonal files sometimes treat rate metrics
              inconsistently. To keep the pipeline defensive, rate columns
              (target_share, air_yards_share, CPOE, EPA metrics) are{" "}
              <span className="text-foreground">mean-aggregated</span> over
              the player&apos;s weeks; counting stats are summed. This makes
              the behavior auditable in one place instead of trusting whatever
              an upstream shipping change happens to do.
            </p>
            <div className="mt-3">
              <Code>
{`rate_cols = {"target_share", "air_yards_share", "wopr",
             "racr", "pacr", "dakota",
             "passing_epa", "rushing_epa", "receiving_epa",
             "passing_cpoe"}

rates  = weekly[rate_cols].mean()       # per-player-season
counts = weekly[other_cols].sum()       # per-player-season`}
              </Code>
            </div>
          </Card>
        </div>
      </Section>

      {/* 3. Features */}
      <Section
        id="features"
        eyebrow="Feature engineering"
        title="42 features, grouped by what they measure"
        description="Features are organized into six conceptual categories so importance analysis tells a story. If target_share is #1 for WRs and td_over_expected is #1 for RBs, we can explain why."
      >
        <FeatureTaxonomy />

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Card title="Target label" subtitle="Shift-by-one join">
            <p className="text-sm text-muted leading-relaxed">
              For a player-season row from year N, the target is their PPG in
              year N+1. We drop rows where the player played fewer than 4
              games in the target season to avoid injury-dominated noise.
            </p>
            <div className="mt-3">
              <Code>
{`next_season["season"] -= 1              # shift back by 1
training = features.merge(
    next_season[["player_id", "season", "target_ppg"]],
    on=["player_id", "season"],
    how="inner",
)`}
              </Code>
            </div>
          </Card>

          <Card title="Scoring formula" subtitle="Full PPR, centralized">
            <p className="text-sm text-muted leading-relaxed">
              One function computes fantasy points everywhere — features,
              targets, baselines. Changing scoring requires editing a single
              file.
            </p>
            <div className="mt-3">
              <Code>
{`points = (
    pass_yards * 0.04 + pass_td * 4 + interceptions * -1
  + rush_yards * 0.10 + rush_td * 6
  + receptions * 1.0 + rec_yards * 0.10 + rec_td * 6
  + fumbles_lost * -2
)`}
              </Code>
            </div>
          </Card>
        </div>
      </Section>

      {/* 4. Models */}
      <Section
        id="models"
        eyebrow="Layer 2 · Point estimates"
        title="Position-specific XGBoost"
        description="Four separate regressors — QB, RB, WR, TE — each tuned on its own hyperparameter grid. RBs learn different signal than WRs; one model for all positions would be a worse model for every position."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Why XGBoost?">
            <ul className="space-y-2 text-sm text-muted">
              <li>
                <span className="text-foreground">Tabular sweet spot.</span>{" "}
                Gradient-boosted trees dominate on structured tabular data
                of this size; no neural net is going to outperform it with
                6k rows and 42 features.
              </li>
              <li>
                <span className="text-foreground">Interpretable.</span>{" "}
                SHAP / gain importance plugs directly in — &ldquo;why this
                player?&rdquo; has a real answer.
              </li>
              <li>
                <span className="text-foreground">Handles missingness</span>{" "}
                natively, which matters for rookies and partial seasons.
              </li>
            </ul>
          </Card>

          <Card title="Per-position hyperparameters">
            <div className="text-xs text-muted mb-2">
              Tuned via grid search with time-series cross-validation; stored
              in TUNED_PARAMS and loaded by the training and inference paths.
            </div>
            <Code>
{`QB: depth=4  lr=0.05  min_child=5   subsample=0.8
RB: depth=3  lr=0.02  min_child=5   subsample=0.9
WR: depth=3  lr=0.02  min_child=10  subsample=0.7
TE: depth=6  lr=0.02  min_child=10  subsample=0.9`}
            </Code>
          </Card>
        </div>
      </Section>

      {/* 5. Bayesian */}
      <Section
        id="bayesian"
        eyebrow="Layer 3 · Uncertainty"
        title="Bayesian updating with calibration"
        description="XGBoost gives a point estimate. We want a full distribution. The Bayesian layer takes the model prediction, combines it with each player's historical prior, and produces a calibrated μ / σ."
      >
        <BayesianBlendDiagram />

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <Card title="Blending logic">
            <div className="text-sm text-muted leading-relaxed space-y-2">
              <p>
                Normal-normal conjugate update. The prior precision scales
                with √n_seasons so a 10-year vet and a 2nd-year player
                aren&apos;t trusted equally. The XGBoost weight is capped at
                85% — enough to dominate, but the prior still prevents wild
                predictions on stable veterans.
              </p>
              <p>
                <span className="text-foreground">Rookies</span> (no prior
                history) get 100% model weight and a slightly wider σ to
                reflect that we genuinely know less.
              </p>
            </div>
          </Card>

          <Card title="Calibration step">
            <div className="text-sm text-muted leading-relaxed space-y-2">
              <p>
                Before the real backtest window, 2017–2018 is spent learning a
                single scalar: the std-dev multiplier that makes our empirical
                z-scores match a standard normal.
              </p>
              <p>
                Without this step, stated confidence intervals would be too
                tight. With it, an 80% interval actually covers the truth ~80%
                of the time — measured on out-of-sample data.
              </p>
              <div>
                <Code>
{`z_scores     = (y - bay_preds) / bay_stds
cal_scale    = np.std(z_scores)  # > 1 ⇒ model was overconfident
posterior_σ *= cal_scale`}
                </Code>
              </div>
            </div>
          </Card>
        </div>
      </Section>

      {/* 6. Monte Carlo */}
      <Section
        id="montecarlo"
        eyebrow="Layer 4 · Distributions"
        title="10,000 Monte Carlo simulations per player"
        description="Point estimates are weak draft inputs. A high-floor RB and a boom/bust WR can have the same median but require completely different draft-strategy treatment. We sample 10k simulated seasons per player from the Bayesian posterior and derive percentiles from the empirical distribution."
      >
        <DistributionDiagram />

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <Card title="Why skew-normal?">
            <p className="text-sm text-muted leading-relaxed">
              Fantasy outcomes aren&apos;t symmetric: there&apos;s a hard
              floor near zero (can&apos;t score negative PPG over a season)
              and an open right tail (breakout seasons). Skew parameter
              varies by position — TEs have the heaviest right tail (most
              are replacement-level, a few go supernova).
            </p>
          </Card>
          <Card title="Boom / bust">
            <p className="text-sm text-muted leading-relaxed">
              Boom = P(PPG ≥ top-12 threshold). Bust = P(PPG ≤ outside
              top-36). Thresholds are calibrated against 2022–2024
              end-of-season ranks so &ldquo;boom&rdquo; actually means
              finishing as an elite starter, not an arbitrary points number.
            </p>
          </Card>
          <Card title="Draft usefulness">
            <p className="text-sm text-muted leading-relaxed">
              The floor / ceiling / boom / bust set becomes a real decision
              input: high-floor players for safe anchors, high-ceiling
              players when you&apos;re chasing upside, avoid high-bust
              players in the early rounds.
            </p>
          </Card>
        </div>
      </Section>

      {/* 7. VOR */}
      <Section
        id="vor"
        eyebrow="Layer 5 · Ranking"
        title="Value Over Replacement"
        description="Points projections aren't draftable rankings by themselves — positional scarcity matters. VOR subtracts the replacement-level projection from each player's projection, which makes cross-position comparison honest."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Replacement level">
            <p className="text-sm text-muted leading-relaxed mb-3">
              Replacement level is the Nth player at each position, where N =
              league_size × starters_at_position. For a 12-team league with
              FLEX (RB/WR/TE) treated as RB/WR inflation:
            </p>
            <div className="space-y-1 font-mono text-sm">
              <div className="flex justify-between border-b border-card-border/50 py-1">
                <span>QB</span>
                <span className="text-muted">QB13 (12×1 + 1)</span>
              </div>
              <div className="flex justify-between border-b border-card-border/50 py-1">
                <span>RB</span>
                <span className="text-muted">RB37 (12×(2+1) + 1)</span>
              </div>
              <div className="flex justify-between border-b border-card-border/50 py-1">
                <span>WR</span>
                <span className="text-muted">WR37 (12×(2+1) + 1)</span>
              </div>
              <div className="flex justify-between py-1">
                <span>TE</span>
                <span className="text-muted">TE13 (12×1 + 1)</span>
              </div>
            </div>
          </Card>

          <Card title="Why it matters">
            <p className="text-sm text-muted leading-relaxed">
              A QB who projects for 22 PPG vs a WR who projects for 16 PPG
              isn&apos;t an obvious pick — it depends on how much the next
              available QB and WR project for. VOR removes the positional
              baseline and gives you the number that actually drives roster
              construction. All league settings (team count, slots, FLEX)
              feed back into replacement level dynamically in the API.
            </p>
            <div className="mt-3">
              <Code>
{`replacement_rank = {
    "QB": league_size * qb_slots + 1,
    "RB": league_size * (rb_slots + flex_slots) + 1,
    "WR": league_size * (wr_slots + flex_slots) + 1,
    "TE": league_size * te_slots + 1,
}
vor = player_proj - replacement_proj`}
              </Code>
            </div>
          </Card>
        </div>
      </Section>

      {/* 8. Validation */}
      <Section
        id="validation"
        eyebrow="Evaluation"
        title="Walk-forward validation — no future leakage, ever"
        description="For every target season Y in the backtest, only data from seasons strictly before Y is available to the model. This is the hardest possible evaluation for a time-series problem and it matches production behavior exactly."
      >
        <WalkForwardDiagram />

        <div className="mt-6">
          <Card title="Headline results, 2021–2025">
            <div className="grid gap-4 md:grid-cols-3">
              <Stat value="2.58" label="Model MAE (PPG)" hint="beats naive by 5.5%" />
              <Stat value="0.805" label="Rank correlation ρ" hint="vs naive 0.791" />
              <Stat value="0.671" label="R² overall" hint="vs naive 0.602" />
            </div>
            <p className="mt-4 text-sm text-muted">
              Full year-by-year and per-position breakdown — including the
              current-year comparison against FantasyPros consensus — lives on
              the{" "}
              <Link
                href="/performance"
                className="text-accent underline-offset-4 hover:underline"
              >
                Performance page
              </Link>
              .
            </p>
          </Card>
        </div>
      </Section>

      {/* 9. Stack */}
      <Section
        id="stack"
        eyebrow="Engineering"
        title="Tech stack"
        description="Every layer is chosen for a specific reason — not trend-chasing."
      >
        <TechStack />
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Card title="Reproducibility">
            <ul className="space-y-1 text-sm text-muted">
              <li>Parquet caches for every pipeline stage</li>
              <li>Pinned requirements.txt</li>
              <li>Modules runnable standalone: <code className="font-mono text-xs bg-background px-1 rounded">python -m src.models.xgb</code></li>
              <li>Deterministic: fixed random seeds across XGBoost and NumPy</li>
            </ul>
          </Card>
          <Card title="Code quality">
            <ul className="space-y-1 text-sm text-muted">
              <li>Type hints on public signatures</li>
              <li>Docstrings on every module explaining <em>why</em></li>
              <li>Strict separation: pipeline / models / api / frontend</li>
              <li>No notebooks in the shipped repo — everything importable</li>
            </ul>
          </Card>
        </div>
      </Section>

      {/* Footer CTA */}
      <section className="rounded-xl border border-accent/30 bg-gradient-to-br from-accent/10 to-transparent p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-lg font-semibold">See the numbers</div>
            <div className="text-sm text-muted mt-0.5">
              Walk-forward backtest results and the current-year vs FantasyPros
              comparison.
            </div>
          </div>
          <Link
            href="/performance"
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
          >
            View Performance →
          </Link>
        </div>
      </section>
    </div>
  );
}
