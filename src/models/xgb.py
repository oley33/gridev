"""Position-specific XGBoost models with walk-forward validation.

Trains one XGBoost regressor per position (QB, RB, WR, TE) to predict
next-season PPR points per game. Uses strict walk-forward validation:
train on [2012, Y-1], predict Y, never leaking future data.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

from src.pipeline.targets import build_training_data

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
POSITIONS = ["QB", "RB", "WR", "TE"]

# Features used for modeling — everything except identifiers and targets
ID_COLS = [
    "player_id", "player_display_name", "season", "position", "team", "games",
    "fantasy_points_ppr_calc", "ppg",
    "target_total_pts", "target_ppg", "target_games",
]

# Walk-forward test years: 2019-2023 gives us 7+ years of training data minimum
TEST_YEARS = list(range(2019, 2024))

# Per-position tuned hyperparameters (from tune_xgb.py, validated on holdout)
TUNED_PARAMS = {
    "QB": {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
    },
    "RB": {
        "n_estimators": 200,
        "max_depth": 3,
        "learning_rate": 0.02,
        "min_child_weight": 5,
        "subsample": 0.9,
        "colsample_bytree": 1.0,
    },
    "WR": {
        "n_estimators": 200,
        "max_depth": 3,
        "learning_rate": 0.02,
        "min_child_weight": 10,
        "subsample": 0.7,
        "colsample_bytree": 0.6,
    },
    "TE": {
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.02,
        "min_child_weight": 10,
        "subsample": 0.9,
        "colsample_bytree": 1.0,
    },
}

FIXED_PARAMS = {
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "verbosity": 0,
}


def get_feature_cols(df: pd.DataFrame) -> list[str]:
    """Return all columns that are model features (not IDs or targets)."""
    return [c for c in df.columns if c not in ID_COLS]


def train_and_evaluate(force: bool = False) -> dict:
    """Train position-specific XGBoost models with walk-forward validation.

    Returns a dict with:
        - "results": per-position, per-year evaluation metrics
        - "importance": feature importance per position
        - "predictions": all out-of-sample predictions
        - "summary": aggregated metrics per position
    """
    print("Loading training data...")
    data = build_training_data(force=force)
    feature_cols = get_feature_cols(data)

    print(f"Features ({len(feature_cols)}): {feature_cols}")
    print(f"Test years: {TEST_YEARS}")
    print()

    all_results = []
    all_predictions = []
    all_importance = {}

    for pos in POSITIONS:
        print(f"{'='*60}")
        print(f"  {pos}")
        print(f"{'='*60}")

        pos_data = data[data["position"] == pos].copy()

        pos_predictions = []
        pos_results = []

        for test_year in TEST_YEARS:
            train = pos_data[pos_data["season"] < test_year]
            test = pos_data[pos_data["season"] == test_year]

            if len(test) == 0:
                continue

            X_train = train[feature_cols].values
            y_train = train["target_ppg"].values
            X_test = test[feature_cols].values
            y_test = test["target_ppg"].values

            model = XGBRegressor(**TUNED_PARAMS[pos], **FIXED_PARAMS)

            model.fit(X_train, y_train)
            preds = model.predict(X_test)

            # Metrics
            mae = np.mean(np.abs(y_test - preds))
            mse = np.mean((y_test - preds) ** 2)
            rmse = np.sqrt(mse)

            # R² (can be negative if model is worse than predicting the mean)
            ss_res = np.sum((y_test - preds) ** 2)
            ss_tot = np.sum((y_test - y_test.mean()) ** 2)
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # Spearman rank correlation
            if len(y_test) > 2:
                rho, p_val = spearmanr(y_test, preds)
            else:
                rho, p_val = 0, 1

            result = {
                "position": pos,
                "test_year": test_year,
                "train_size": len(train),
                "test_size": len(test),
                "mae": mae,
                "rmse": rmse,
                "r2": r2,
                "spearman_rho": rho,
                "spearman_p": p_val,
            }
            pos_results.append(result)

            print(f"  {test_year}: MAE={mae:.2f}  RMSE={rmse:.2f}  "
                  f"R²={r2:.3f}  rho={rho:.3f}  (n={len(test)})")

            # Store predictions
            pred_df = test[["player_id", "player_display_name", "season", "position"]].copy()
            pred_df["predicted_ppg"] = preds
            pred_df["actual_ppg"] = y_test
            pred_df["error"] = preds - y_test
            pred_df["abs_error"] = np.abs(pred_df["error"])
            pos_predictions.append(pred_df)

        # Feature importance from the final model (trained on all data up to 2023)
        importance = dict(zip(feature_cols, model.feature_importances_))
        all_importance[pos] = importance

        all_results.extend(pos_results)
        all_predictions.extend(pos_predictions)

        # Position summary
        pos_df = pd.DataFrame(pos_results)
        print(f"\n  {pos} AVERAGE: MAE={pos_df['mae'].mean():.2f}  "
              f"R²={pos_df['r2'].mean():.3f}  rho={pos_df['spearman_rho'].mean():.3f}")
        print()

    # --- Baseline comparison: "just predict last year's PPG" ---
    print(f"{'='*60}")
    print("  NAIVE BASELINE: predict next year = this year's PPG")
    print(f"{'='*60}")

    for pos in POSITIONS:
        pos_data = data[data["position"] == pos]
        test_data = pos_data[pos_data["season"].isin(TEST_YEARS)]
        if len(test_data) == 0:
            continue
        baseline_mae = np.mean(np.abs(test_data["ppg"] - test_data["target_ppg"]))
        baseline_rho, _ = spearmanr(test_data["ppg"], test_data["target_ppg"])
        print(f"  {pos}: MAE={baseline_mae:.2f}  rho={baseline_rho:.3f}")

    # --- Aggregate results ---
    results_df = pd.DataFrame(all_results)
    predictions_df = pd.concat(all_predictions, ignore_index=True)

    summary = (
        results_df.groupby("position")
        .agg(
            avg_mae=("mae", "mean"),
            avg_rmse=("rmse", "mean"),
            avg_r2=("r2", "mean"),
            avg_spearman=("spearman_rho", "mean"),
        )
        .round(3)
    )

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(summary.to_string())

    # --- Top feature importance ---
    print(f"\n{'='*60}")
    print("  TOP 10 FEATURES BY POSITION")
    print(f"{'='*60}")
    for pos in POSITIONS:
        imp = all_importance[pos]
        top = sorted(imp.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"\n  {pos}:")
        for feat, score in top:
            print(f"    {feat:30s} {score:.4f}")

    # --- Biggest misses (for debugging) ---
    print(f"\n{'='*60}")
    print("  BIGGEST PREDICTION MISSES (|error| > 10 PPG)")
    print(f"{'='*60}")
    big_misses = predictions_df[predictions_df["abs_error"] > 10].sort_values(
        "abs_error", ascending=False
    )
    if len(big_misses) > 0:
        for _, row in big_misses.head(15).iterrows():
            direction = "over" if row["error"] > 0 else "under"
            print(f"  {row['season']+1} {row['player_display_name']:25s} ({row['position']}): "
                  f"predicted {row['predicted_ppg']:.1f}, actual {row['actual_ppg']:.1f} "
                  f"({direction} by {row['abs_error']:.1f})")
    else:
        print("  None — model is well calibrated!")

    return {
        "results": results_df,
        "importance": all_importance,
        "predictions": predictions_df,
        "summary": summary,
    }


if __name__ == "__main__":
    train_and_evaluate(force=False)
