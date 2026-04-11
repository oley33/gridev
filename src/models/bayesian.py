"""Bayesian updating layer for projection uncertainty.

Takes XGBoost point estimates and converts them into distributions by
combining the model prediction (likelihood) with a prior built from the
player's historical performance. More seasons of data = tighter intervals.

The key insight: a 3-year veteran with stable production deserves a tighter
confidence interval than a 2nd-year player coming off one good season.

Calibration: uses cross-validated residuals to estimate true model uncertainty,
and an empirical calibration step so that stated confidence intervals actually
match observed coverage.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.model_selection import cross_val_predict

from src.pipeline.targets import build_training_data
from src.models.xgb import get_feature_cols, TEST_YEARS, POSITIONS, TUNED_PARAMS, FIXED_PARAMS

from xgboost import XGBRegressor

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"

# Years used to learn the calibration scaling factor before the real test window.
# We "spend" 2017-2018 on calibration so 2019-2023 results are honest.
CALIBRATION_YEARS = [2017, 2018]


def _build_player_history(data: pd.DataFrame) -> pd.DataFrame:
    """Build per-player historical PPG stats up to each season.

    For each player-season, compute the mean and std of their PPG
    from all prior seasons. This becomes the Bayesian prior.
    """
    records = []
    grouped = data.groupby("player_id")

    for player_id, group in grouped:
        group = group.sort_values("season")
        ppg_values = group["ppg"].values
        seasons = group["season"].values

        for i in range(len(group)):
            history = ppg_values[:i]

            if len(history) == 0:
                prior_mean = np.nan
                prior_std = np.nan
                n_prior_seasons = 0
            else:
                prior_mean = np.mean(history)
                prior_std = np.std(history, ddof=1) if len(history) > 1 else np.nan
                n_prior_seasons = len(history)

            records.append({
                "player_id": player_id,
                "season": seasons[i],
                "prior_mean": prior_mean,
                "prior_std": prior_std,
                "n_prior_seasons": n_prior_seasons,
            })

    return pd.DataFrame(records)


def _get_position_priors(data: pd.DataFrame) -> dict[str, tuple[float, float]]:
    """Compute position-level mean and std of PPG."""
    priors = {}
    for pos in POSITIONS:
        pos_data = data[data["position"] == pos]["ppg"]
        priors[pos] = (pos_data.mean(), pos_data.std())
    return priors


def _estimate_model_std_cv(
    model: XGBRegressor, X_train: np.ndarray, y_train: np.ndarray
) -> float:
    """Estimate model prediction uncertainty using cross-validated residuals.

    In-sample residuals underestimate true error because XGBoost overfits
    the training set. 5-fold CV residuals give a much more honest estimate.
    """
    cv_preds = cross_val_predict(model, X_train, y_train, cv=5)
    return np.std(y_train - cv_preds)


def bayesian_update(
    xgb_pred: float,
    model_std: float,
    prior_mean: float,
    prior_std: float,
    n_prior_seasons: int,
) -> tuple[float, float]:
    """Combine XGBoost prediction with player history using Bayesian updating.

    Uses normal-normal conjugate prior. The weight given to the model vs
    the prior depends on relative precision and amount of history.
    """
    prior_precision = 1.0 / (prior_std ** 2) if prior_std > 0 else 0
    model_precision = 1.0 / (model_std ** 2)

    # Scale prior precision by amount of history — sqrt to avoid over-weighting
    effective_prior_precision = prior_precision * np.sqrt(n_prior_seasons)

    total_precision = effective_prior_precision + model_precision

    posterior_mean = (
        (effective_prior_precision * prior_mean + model_precision * xgb_pred)
        / total_precision
    )
    posterior_std = np.sqrt(1.0 / total_precision)

    return posterior_mean, posterior_std


def _run_one_year(
    pos_data: pd.DataFrame,
    feature_cols: list[str],
    history: pd.DataFrame,
    pos_prior_mean: float,
    pos_prior_std: float,
    test_year: int,
    pos: str = "QB",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, XGBRegressor]:
    """Train XGBoost on data before test_year, predict test_year, return raw posteriors.

    The Bayesian update adjusts the point estimate (posterior mean) using the
    CV-estimated model_std for weighting. The output uncertainty (posterior_std)
    is computed separately and more honestly — it represents true prediction
    uncertainty, not the narrowed posterior from conjugate updating.
    """
    train = pos_data[pos_data["season"] < test_year]
    test = pos_data[pos_data["season"] == test_year]

    X_train = train[feature_cols].values
    y_train = train["target_ppg"].values
    X_test = test[feature_cols].values
    y_test = test["target_ppg"].values

    model = XGBRegressor(**TUNED_PARAMS[pos], **FIXED_PARAMS)
    model.fit(X_train, y_train)
    xgb_preds = model.predict(X_test)

    # Cross-validated residual std — honest estimate of model uncertainty
    model_std = _estimate_model_std_cv(model, X_train, y_train)

    # Bayesian update for each player
    test_with_history = test.merge(history, on=["player_id", "season"], how="left")

    bayesian_preds = []
    bayesian_stds = []

    for xgb_pred, row in zip(xgb_preds, test_with_history.itertuples()):
        p_mean = row.prior_mean if pd.notna(row.prior_mean) else pos_prior_mean
        p_std = row.prior_std if pd.notna(row.prior_std) else pos_prior_std
        n_seasons = row.n_prior_seasons if pd.notna(row.n_prior_seasons) else 0

        # Floor on prior_std
        p_std = max(p_std if not np.isnan(p_std) else pos_prior_std, 1.5)

        if n_seasons == 0:
            # No history — trust model, wider uncertainty for unknowns
            bayesian_preds.append(xgb_pred)
            bayesian_stds.append(model_std * 1.2)
        else:
            # Point estimate: lightly blend XGBoost with prior.
            # XGBoost is the better predictor, so weight it heavily (85%).
            # The prior only nudges — it prevents wild predictions for
            # stable veterans, without dragging accurate predictions off.
            blend_weight = 0.85
            blended = blend_weight * xgb_pred + (1 - blend_weight) * p_mean
            bayesian_preds.append(blended)

            # Uncertainty: based on model_std, adjusted per player.
            # More seasons of stable data = tighter interval, but never
            # narrower than model_std * 0.7 (irreducible prediction noise).
            history_shrink = 1.0 / (1.0 + 0.15 * n_seasons)
            player_std = model_std * max(history_shrink, 0.7)

            # Players with high historical variance get wider intervals
            volatility_boost = min(p_std / pos_prior_std, 2.0)
            player_std *= volatility_boost

            bayesian_stds.append(player_std)

    return (
        xgb_preds,
        np.array(bayesian_preds),
        np.array(bayesian_stds),
        y_test,
        model,
    )


def _learn_calibration_scale(
    pos_data: pd.DataFrame,
    feature_cols: list[str],
    history: pd.DataFrame,
    pos_prior_mean: float,
    pos_prior_std: float,
    pos: str = "QB",
) -> float:
    """Learn the std scaling factor from calibration years.

    Runs walk-forward on CALIBRATION_YEARS, collects z-scores, and finds the
    factor that makes them standard normal. If a perfectly calibrated model
    has z ~ N(0,1), and our z-scores have empirical std of S, then we need
    to multiply all posterior_stds by S to fix calibration.
    """
    all_z_scores = []

    for cal_year in CALIBRATION_YEARS:
        test = pos_data[pos_data["season"] == cal_year]
        if len(test) == 0:
            continue

        xgb_preds, bay_preds, bay_stds, y_test, _ = _run_one_year(
            pos_data, feature_cols, history, pos_prior_mean, pos_prior_std, cal_year, pos
        )

        z = (y_test - bay_preds) / bay_stds
        all_z_scores.extend(z.tolist())

    if len(all_z_scores) < 10:
        return 1.0  # not enough data, don't scale

    # The empirical std of z-scores tells us how much to widen
    return np.std(all_z_scores)


def train_and_evaluate(force: bool = False) -> dict:
    """Run XGBoost + calibrated Bayesian updating with walk-forward validation."""
    print("Loading training data...")
    data = build_training_data(force=force)
    feature_cols = get_feature_cols(data)

    from src.pipeline.features import build_feature_matrix
    all_features = build_feature_matrix(force=force)

    print("Building player history priors...")
    history = _build_player_history(all_features)
    position_priors = _get_position_priors(all_features)

    print(f"Calibration years: {CALIBRATION_YEARS}")
    print(f"Test years: {TEST_YEARS}")
    print()

    all_results = []
    all_predictions = []

    for pos in POSITIONS:
        print(f"{'='*60}")
        print(f"  {pos}")
        print(f"{'='*60}")

        pos_data = data[data["position"] == pos].copy()
        pos_prior_mean, pos_prior_std = position_priors[pos]

        # --- Learn calibration scaling factor ---
        cal_scale = _learn_calibration_scale(
            pos_data, feature_cols, history, pos_prior_mean, pos_prior_std, pos
        )
        print(f"  Calibration scale factor: {cal_scale:.2f} "
              f"(1.0 = perfect, >1 = was overconfident)")

        for test_year in TEST_YEARS:
            test = pos_data[pos_data["season"] == test_year]
            if len(test) == 0:
                continue

            xgb_preds, bay_preds, bay_stds, y_test, model = _run_one_year(
                pos_data, feature_cols, history, pos_prior_mean, pos_prior_std, test_year, pos
            )

            # Apply calibration: widen stds by the learned factor
            calibrated_stds = bay_stds * cal_scale

            # --- Metrics ---
            xgb_mae = np.mean(np.abs(y_test - xgb_preds))
            bay_mae = np.mean(np.abs(y_test - bay_preds))
            baseline_mae = np.mean(np.abs(test["ppg"].values - y_test))

            xgb_rho, _ = spearmanr(y_test, xgb_preds) if len(y_test) > 2 else (0, 1)
            bay_rho, _ = spearmanr(y_test, bay_preds) if len(y_test) > 2 else (0, 1)
            baseline_rho, _ = spearmanr(y_test, test["ppg"].values) if len(y_test) > 2 else (0, 1)

            # Calibration with corrected stds
            z_scores = (y_test - bay_preds) / calibrated_stds
            within_50 = np.mean(np.abs(z_scores) <= 0.674)
            within_80 = np.mean(np.abs(z_scores) <= 1.282)
            within_90 = np.mean(np.abs(z_scores) <= 1.645)

            result = {
                "position": pos,
                "test_year": test_year,
                "n": len(test),
                "cal_scale": cal_scale,
                "xgb_mae": xgb_mae,
                "bayesian_mae": bay_mae,
                "baseline_mae": baseline_mae,
                "xgb_rho": xgb_rho,
                "bayesian_rho": bay_rho,
                "baseline_rho": baseline_rho,
                "cal_50": within_50,
                "cal_80": within_80,
                "cal_90": within_90,
            }
            all_results.append(result)

            print(f"  {test_year} (n={len(test):3d}): "
                  f"MAE  xgb={xgb_mae:.2f}  bayes={bay_mae:.2f}  base={baseline_mae:.2f} | "
                  f"rho  xgb={xgb_rho:.3f}  bayes={bay_rho:.3f}  base={baseline_rho:.3f} | "
                  f"cal 50/80/90: {within_50:.0%}/{within_80:.0%}/{within_90:.0%}")

            # Store predictions
            pred_df = test[["player_id", "player_display_name", "season", "position"]].copy()
            pred_df["xgb_pred"] = xgb_preds
            pred_df["bayesian_pred"] = bay_preds
            pred_df["bayesian_std"] = calibrated_stds
            pred_df["actual_ppg"] = y_test
            pred_df["floor_p10"] = bay_preds - 1.282 * calibrated_stds
            pred_df["ceiling_p90"] = bay_preds + 1.282 * calibrated_stds
            all_predictions.append(pred_df)

        print()

    # --- Summary ---
    results_df = pd.DataFrame(all_results)
    predictions_df = pd.concat(all_predictions, ignore_index=True)

    print(f"\n{'='*60}")
    print("  SUMMARY BY POSITION (averaged across test years)")
    print(f"{'='*60}")

    summary = results_df.groupby("position").agg(
        xgb_mae=("xgb_mae", "mean"),
        bayesian_mae=("bayesian_mae", "mean"),
        baseline_mae=("baseline_mae", "mean"),
        xgb_rho=("xgb_rho", "mean"),
        bayesian_rho=("bayesian_rho", "mean"),
        baseline_rho=("baseline_rho", "mean"),
        cal_scale=("cal_scale", "first"),
        cal_50=("cal_50", "mean"),
        cal_80=("cal_80", "mean"),
        cal_90=("cal_90", "mean"),
    ).round(3)

    print("\n  MAE (lower is better):")
    print(f"  {'Position':<8} {'XGBoost':>8} {'Bayesian':>8} {'Baseline':>8} {'Bayes vs Base':>14}")
    for pos in POSITIONS:
        row = summary.loc[pos]
        improvement = (1 - row["bayesian_mae"] / row["baseline_mae"]) * 100
        print(f"  {pos:<8} {row['xgb_mae']:>8.2f} {row['bayesian_mae']:>8.2f} "
              f"{row['baseline_mae']:>8.2f} {improvement:>+13.1f}%")

    print("\n  Rank Correlation (higher is better):")
    print(f"  {'Position':<8} {'XGBoost':>8} {'Bayesian':>8} {'Baseline':>8}")
    for pos in POSITIONS:
        row = summary.loc[pos]
        print(f"  {pos:<8} {row['xgb_rho']:>8.3f} {row['bayesian_rho']:>8.3f} "
              f"{row['baseline_rho']:>8.3f}")

    print("\n  Calibration (target: 50%/80%/90%):")
    print(f"  {'Position':<8} {'Scale':>6} {'50% CI':>8} {'80% CI':>8} {'90% CI':>8}")
    for pos in POSITIONS:
        row = summary.loc[pos]
        print(f"  {pos:<8} {row['cal_scale']:>5.1f}x {row['cal_50']:>7.0%} "
              f"{row['cal_80']:>7.0%} {row['cal_90']:>7.0%}")

    return {
        "results": results_df,
        "predictions": predictions_df,
        "summary": summary,
    }


if __name__ == "__main__":
    train_and_evaluate(force=False)
