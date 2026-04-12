"""Monte Carlo simulation layer.

Takes the Bayesian posterior (mean + calibrated std) for each player and
runs 10,000 simulations to produce full outcome distributions:
- Median projection (p50)
- Floor (p10) and ceiling (p90)
- Boom probability (top-12 finish at position)
- Bust probability (outside top-36 at position)
- Weekly scoring distribution shape

This is where the projections become genuinely useful for draft strategy —
a high-floor RB in round 3 vs a boom/bust WR are completely different picks
depending on your roster construction.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, skewnorm

from src.pipeline.targets import build_training_data
from src.pipeline.features import build_feature_matrix
from src.models.bayesian import (
    _build_player_history,
    _get_position_priors,
    _run_one_year,
    _learn_calibration_scale,
)
from src.models.xgb import get_feature_cols, TEST_YEARS, POSITIONS

N_SIMS = 10_000
RNG = np.random.default_rng(42)

# Boom/bust thresholds by position (PPG, full PPR, 12-team league)
# Boom = roughly top-12 at position, Bust = outside startable range (≈ beyond
# QB12 / RB36 / WR36 / TE12). Calibrated against 2022-2024 end-of-season ranks.
BOOM_THRESHOLDS = {"QB": 20.0, "RB": 16.0, "WR": 15.0, "TE": 11.0}
BUST_THRESHOLDS = {"QB": 14.0, "RB": 9.0, "WR": 9.0, "TE": 6.0}


def _simulate_player(
    pred_mean: float,
    pred_std: float,
    pos: str,
    n_sims: int = N_SIMS,
) -> dict:
    """Run Monte Carlo simulation for a single player.

    Uses a skew-normal distribution rather than pure normal because
    fantasy outcomes have a natural floor near 0 and a long right tail
    (breakout seasons). The skew is position-dependent:
    - RBs: moderate right skew (bellcow upside, committee floor)
    - WRs: slight right skew (volume is more stable)
    - TEs: high right skew (most are replacement-level, few elite)
    - QBs: near-symmetric (scoring is steadier)
    """
    skew_by_pos = {"QB": 1.0, "RB": 2.0, "WR": 1.5, "TE": 2.5}
    skew = skew_by_pos.get(pos, 1.5)

    # skewnorm parameterization: a=skewness, loc=mean, scale=std
    # Adjust loc so that the median of the skew-normal matches pred_mean
    samples = skewnorm.rvs(a=skew, loc=pred_mean, scale=pred_std, size=n_sims, random_state=RNG)

    # Floor at 0 — can't score negative PPG over a season
    samples = np.clip(samples, 0, None)

    # Shift so median matches the Bayesian prediction
    median_shift = pred_mean - np.median(samples)
    samples = np.clip(samples + median_shift, 0, None)

    boom_threshold = BOOM_THRESHOLDS[pos]
    bust_threshold = BUST_THRESHOLDS[pos]

    return {
        "sim_median": np.median(samples),
        "sim_mean": np.mean(samples),
        "sim_p10": np.percentile(samples, 10),  # floor
        "sim_p25": np.percentile(samples, 25),
        "sim_p75": np.percentile(samples, 75),
        "sim_p90": np.percentile(samples, 90),  # ceiling
        "sim_std": np.std(samples),
        "boom_pct": np.mean(samples >= boom_threshold),
        "bust_pct": np.mean(samples <= bust_threshold),
        "upside_ratio": np.percentile(samples, 90) / max(np.percentile(samples, 10), 0.5),
    }


def run_simulations(force: bool = False) -> dict:
    """Run full pipeline: XGBoost -> Bayesian -> Monte Carlo with walk-forward eval."""
    print("Loading data...")
    data = build_training_data(force=force)
    all_features = build_feature_matrix(force=force)
    feature_cols = get_feature_cols(data)

    print("Building player history priors...")
    history = _build_player_history(all_features)
    position_priors = _get_position_priors(all_features)

    print(f"Running {N_SIMS:,} simulations per player")
    print(f"Test years: {TEST_YEARS}\n")

    all_predictions = []
    all_results = []

    for pos in POSITIONS:
        print(f"{'='*60}")
        print(f"  {pos}")
        print(f"{'='*60}")

        pos_data = data[data["position"] == pos].copy()
        pos_prior_mean, pos_prior_std = position_priors[pos]

        cal_scale = _learn_calibration_scale(
            pos_data, feature_cols, history, pos_prior_mean, pos_prior_std, pos
        )

        for test_year in TEST_YEARS:
            test = pos_data[pos_data["season"] == test_year]
            if len(test) == 0:
                continue

            xgb_preds, bay_preds, bay_stds, y_test, model = _run_one_year(
                pos_data, feature_cols, history, pos_prior_mean, pos_prior_std, test_year, pos
            )
            calibrated_stds = bay_stds * cal_scale

            # Run Monte Carlo for each player
            sim_results = []
            for pred, std in zip(bay_preds, calibrated_stds):
                sim_results.append(_simulate_player(pred, std, pos))

            sim_df = pd.DataFrame(sim_results)

            # Build prediction dataframe
            pred_df = test[["player_id", "player_display_name", "season", "position"]].copy()
            pred_df["actual_ppg"] = y_test
            pred_df["xgb_pred"] = xgb_preds
            pred_df["bayesian_pred"] = bay_preds
            pred_df["bayesian_std"] = calibrated_stds
            pred_df = pd.concat([pred_df.reset_index(drop=True), sim_df], axis=1)

            all_predictions.append(pred_df)

            # Evaluate simulation quality
            sim_mae = np.mean(np.abs(y_test - sim_df["sim_median"].values))
            sim_rho, _ = spearmanr(y_test, sim_df["sim_median"].values)
            bay_mae = np.mean(np.abs(y_test - bay_preds))
            baseline_mae = np.mean(np.abs(test["ppg"].values - y_test))

            # How often does actual fall within p10-p90 range?
            in_range = np.mean(
                (y_test >= sim_df["sim_p10"].values) & (y_test <= sim_df["sim_p90"].values)
            )

            result = {
                "position": pos, "test_year": test_year, "n": len(test),
                "sim_mae": sim_mae, "bay_mae": bay_mae, "baseline_mae": baseline_mae,
                "sim_rho": sim_rho, "p10_p90_coverage": in_range,
            }
            all_results.append(result)

            print(f"  {test_year} (n={len(test):3d}): "
                  f"MAE sim={sim_mae:.2f} bay={bay_mae:.2f} base={baseline_mae:.2f} | "
                  f"rho={sim_rho:.3f} | p10-p90 coverage: {in_range:.0%}")

        print()

    predictions_df = pd.concat(all_predictions, ignore_index=True)
    results_df = pd.DataFrame(all_results)

    # --- Summary ---
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    summary = results_df.groupby("position").agg(
        sim_mae=("sim_mae", "mean"),
        bay_mae=("bay_mae", "mean"),
        baseline_mae=("baseline_mae", "mean"),
        sim_rho=("sim_rho", "mean"),
        p10_p90_coverage=("p10_p90_coverage", "mean"),
    ).round(3)

    print("\n  MAE:")
    print(f"  {'Pos':<5} {'MC Sim':>7} {'Bayes':>7} {'Base':>7} {'MC vs Base':>11}")
    for pos in POSITIONS:
        row = summary.loc[pos]
        imp = (1 - row["sim_mae"] / row["baseline_mae"]) * 100
        print(f"  {pos:<5} {row['sim_mae']:>7.2f} {row['bay_mae']:>7.2f} "
              f"{row['baseline_mae']:>7.2f} {imp:>+10.1f}%")

    print(f"\n  Rank Correlation & Coverage:")
    print(f"  {'Pos':<5} {'rho':>7} {'p10-p90':>9}")
    for pos in POSITIONS:
        row = summary.loc[pos]
        print(f"  {pos:<5} {row['sim_rho']:>7.3f} {row['p10_p90_coverage']:>8.0%}")

    # --- Show example projections for most recent test year ---
    latest = predictions_df[predictions_df["season"] == max(TEST_YEARS) - 1]
    print(f"\n{'='*60}")
    print(f"  SAMPLE PROJECTIONS ({max(TEST_YEARS)} season)")
    print(f"{'='*60}")

    for pos in POSITIONS:
        pos_latest = latest[latest["position"] == pos].sort_values("sim_median", ascending=False)
        print(f"\n  Top 10 {pos}:")
        print(f"  {'Player':<25} {'Proj':>5} {'Floor':>6} {'Ceil':>6} "
              f"{'Boom':>6} {'Bust':>6} {'Actual':>7}")

        for _, row in pos_latest.head(10).iterrows():
            name = str(row["player_display_name"])[:24]
            print(f"  {name:<25} {row['sim_median']:>5.1f} {row['sim_p10']:>6.1f} "
                  f"{row['sim_p90']:>6.1f} {row['boom_pct']:>5.0%} "
                  f"{row['bust_pct']:>5.0%} {row['actual_ppg']:>7.1f}")

    return {
        "results": results_df,
        "predictions": predictions_df,
        "summary": summary,
    }


if __name__ == "__main__":
    run_simulations(force=False)
