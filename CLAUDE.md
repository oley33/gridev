# FF Projections — Fantasy Football Draft Assistant

## What This Project Is

A full-stack fantasy football draft assistant that generates player projections using
an ensemble ML pipeline and surfaces them through a real-time draft board UI. The core
value proposition: projections built from first principles (not just regurgitating
FantasyPros consensus) with quantified uncertainty — floor, ceiling, and boom/bust
probability for every player.

Scoring format: **Full PPR** (1 point per reception).

## Project Goals & Audience

This is a personal project with two audiences:

1. **The owner** — an actual fantasy football player who will use this tool during
   their real draft. It needs to actually work and produce useful recommendations,
   not just look good on paper.
2. **Tech recruiters and hiring managers** — this lives on GitHub as a portfolio piece.
   Code quality, clear architecture, and a good README matter as much as the results.

### What this means for development decisions:
- **Prefer explainability over marginal accuracy gains.** A linear regression with
  clear feature importance is more impressive in an interview than a black-box neural
  net that scores 1% better. If an interviewer asks "why did your model rank this
  player here?", we need a real answer.
- **Clean code over clever code.** Well-structured modules, type hints, docstrings on
  public APIs, and a clear separation of concerns. A recruiter will skim the repo for
  ~60 seconds — the structure should tell the story immediately.
- **Show the work.** Walk-forward backtest results, comparison tables vs baseline,
  feature importance charts — these belong in the README or a results summary. The
  project should prove it works, not just claim to.
- **Ship something usable.** A polished draft board UI that actually functions during
  a live draft is more impressive than a perfect model with no interface. Don't let
  perfectionism on the ML side block building the frontend.
- **README is a first-class deliverable.** It should explain the problem, the approach,
  the results, and how to run it — in that order. A recruiter who reads only the README
  should walk away understanding what this person can build.

## Architecture Overview

```
nfl_data_py (raw stats) ──► Feature Pipeline ──► XGBoost Models (per position)
                                                        │
                                                        ▼
                                                 Bayesian Updating
                                                        │
                                                        ▼
                                                Monte Carlo Sim (10k)
                                                        │
                                                        ▼
                                            Ensemble w/ Consensus ADP
                                                        │
                                                        ▼
                                                  VOR Calculation
                                                        │
                                    ┌───────────────────┼───────────────────┐
                                    ▼                                       ▼
                             FastAPI Backend                         Next.js Draft UI
```

### Layer 1 — Data Pipeline (`src/pipeline/`)
- **fetch.py**: Pull and cache play-by-play, seasonal stats, rosters from nfl_data_py.
  Cache as parquet in `data/raw/`. Seasons 2012–current.
- **features.py**: Build per-player-per-season feature matrix. Output is one row per
  player-season with all engineered features.
- **targets.py**: Build target labels — next-season full PPR fantasy points. This is
  what the models predict.

### Layer 2 — Models (`src/models/`)
- **xgb.py**: Position-specific XGBoost regressors (QB, RB, WR, TE). Trained on the
  feature matrix. Walk-forward validation only — never leak future data.
- **bayesian.py**: Bayesian updating layer. Converts point estimates into distributions
  using Beta/Normal priors updated with observed seasons. More data = tighter intervals.
- **monte_carlo.py**: Run 10k simulations sampling from Bayesian posteriors. Output:
  median, p10 (floor), p90 (ceiling), boom probability (top-12 finish), bust probability
  (outside top-36).
- **ensemble.py**: Blend model output with consensus projections (70/30 split). Final
  projection output.

### Layer 3 — Scoring (`src/scoring/`)
- **fantasy_points.py**: Full PPR scoring formula. Single source of truth for point
  calculations across the entire codebase.
- **vor.py**: Value Over Replacement. Computes replacement level per position based on
  league size and roster construction, then ranks all players by VOR.

### Layer 4 — API (`src/api/`)
- **FastAPI** app exposing projections, rankings, and draft board state.
- Stateless — draft state lives in the frontend.

### Layer 5 — Frontend (`frontend/`)
- **Next.js** draft board UI. Enter league settings, mark players as drafted, get
  live recommendations based on VOR and positional need.

## Key Engineering Features

### Fantasy Points Formula (Full PPR)
```
points = (pass_yards * 0.04) + (pass_td * 4) + (interceptions * -1)
       + (rush_yards * 0.1) + (rush_td * 6)
       + (receptions * 1.0) + (rec_yards * 0.1) + (rec_td * 6)
       + (fumbles_lost * -2)
```

### Feature Matrix (what goes into the models)

**Volume & opportunity:**
- target_share: targets / team_targets
- air_yards_share: air_yards / team_air_yards
- rush_share: carries / team_carries
- snap_pct: snaps / team_offensive_snaps
- redzone_target_share, redzone_rush_share

**Efficiency:**
- yards_per_route_run
- yards_per_carry
- catch_rate, catch_rate_over_expected (CROE)
- true_catch_rate (adjusted for drops/throwaways)

**Situation/context:**
- team_implied_total: Vegas implied points (strongest single team predictor)
- offensive_line_rank
- qb_cpoe: QB completion % over expected (affects all pass catchers)
- defensive_schedule_strength

**Regression indicators:**
- expected_td_rate: red_zone_opportunities * historical_conversion_rate
- td_over_expected: actual_tds - expected_tds (positive = regression candidate)

**Career trajectory:**
- age, years_experience
- position_age_curve_factor (RBs cliff at 26+, WRs peak 25-28)

### VOR — Replacement Level Defaults (12-team, Full PPR)

| Position | Starters | Replacement Player Rank |
|----------|----------|------------------------|
| QB       | 1        | QB13                   |
| RB       | 2        | RB25                   |
| WR       | 2        | WR31                   |
| TE       | 1        | TE13                   |
| FLEX     | 1        | (handled via WR/RB adjustment) |

VOR = player_projected_points - replacement_level_points

### Walk-Forward Validation Protocol

Never train on future data. For each test year Y:
1. Train on seasons [2012, Y-1]
2. Predict season Y
3. Measure MAE, R², and rank correlation vs actual

This means the first testable year is 2013 (trained on 2012 only). Primary evaluation
window: 2019–2024 (trained on 7+ years of data).

## Success Metrics

These are the quantitative benchmarks that determine whether the model is working.

### Primary: Beat Consensus
- **Target**: model MAE < FantasyPros consensus ADP-implied MAE for each position
- **How to measure**: for each test year, convert ADP rank to implied points
  (rank 1 = highest projection), compare MAE against our model's MAE
- **Bar to clear**: even 2-5% improvement over consensus is meaningful — consensus
  is already very good

### Secondary: Calibration
- When the model says "80% confidence interval", the true value should fall in that
  range ~80% of the time
- Measure calibration across all confidence levels (50%, 80%, 90%)
- Miscalibration = overconfident model = useless uncertainty estimates

### Tertiary: Rank Correlation
- Spearman correlation between predicted rank and actual rank, per position
- Target: ρ > 0.60 for WR/RB, ρ > 0.70 for QB (QBs are more predictable)
- TE will be noisy — ρ > 0.45 is acceptable

### Portfolio-Specific Success Metrics
- Clean, documented walk-forward backtest with reproducible results
- Feature importance analysis that tells a coherent story (not a black box)
- Comparison table: our model vs naive baseline vs consensus
- The README shows a recruiter what this is in 30 seconds

## Development Commands

```bash
# Activate virtual environment
source .venv/Scripts/activate   # Windows Git Bash
.venv\Scripts\activate          # Windows CMD

# Run the data pipeline
python -m src.pipeline.fetch
python -m src.pipeline.features
python -m src.pipeline.targets

# Train models
python -m src.models.xgb

# Run API server
uvicorn src.api.main:app --reload

# Run tests
pytest tests/
```

## Conventions

- Python backend, all source in `src/`. Runnable as modules (`python -m src.x.y`).
- pandas DataFrames are the data interchange format between pipeline stages.
- Cache intermediate results as parquet in `data/cache/` to avoid re-fetching.
- Every model file must implement `train()` and `predict()` functions.
- Type hints on all public function signatures.
- Tests in `tests/` mirroring `src/` structure.
- Virtual environment in `.venv/`, never committed.
- No notebooks in the final repo — all logic must be in importable Python modules.
  (Use notebooks locally for EDA, but don't commit them.)

## What NOT to Do

- Do not hardcode season years — always parameterize.
- Do not mix scoring formats — everything is Full PPR, enforced in one place.
- Do not train on test data or allow any future data leakage.
- Do not over-engineer early — get XGBoost working before adding Bayesian/MC layers.
- Do not scrape sites that prohibit it — use nfl_data_py, Sleeper API, and public APIs.
