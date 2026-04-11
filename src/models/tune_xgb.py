"""Hyperparameter tuning for position-specific XGBoost models.

Uses walk-forward validation (same protocol as training) to find optimal
hyperparameters per position. Searches over the most impactful params:
max_depth, learning_rate, n_estimators, subsample, min_child_weight,
colsample_bytree, and regularization.
"""

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

from src.pipeline.targets import build_training_data
from src.models.xgb import get_feature_cols, POSITIONS

# Tune on 2017-2021, hold out 2022-2023 as final validation
# to avoid overfitting hyperparams to our test window
TUNE_YEARS = list(range(2017, 2022))
HOLDOUT_YEARS = [2022, 2023]


PARAM_GRID = {
    "n_estimators": [100, 200, 400],
    "max_depth": [3, 4, 5, 6],
    "learning_rate": [0.02, 0.05, 0.1],
    "min_child_weight": [3, 5, 10],
    "subsample": [0.7, 0.8, 0.9],
    "colsample_bytree": [0.6, 0.8, 1.0],
}

# Fixed params (less impact, keeps search tractable)
FIXED_PARAMS = {
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "random_state": 42,
    "verbosity": 0,
}


@dataclass
class TuneResult:
    position: str
    params: dict
    avg_mae: float
    avg_rho: float
    per_year: list[dict]


def _evaluate_params(
    pos_data: pd.DataFrame,
    feature_cols: list[str],
    params: dict,
    eval_years: list[int],
) -> tuple[float, float, list[dict]]:
    """Evaluate a param set across walk-forward years. Returns (avg_mae, avg_rho, details)."""
    results = []

    for test_year in eval_years:
        train = pos_data[pos_data["season"] < test_year]
        test = pos_data[pos_data["season"] == test_year]
        if len(test) < 5:
            continue

        model = XGBRegressor(**params, **FIXED_PARAMS)
        model.fit(train[feature_cols].values, train["target_ppg"].values)
        preds = model.predict(test[feature_cols].values)
        y_test = test["target_ppg"].values

        mae = np.mean(np.abs(y_test - preds))
        rho, _ = spearmanr(y_test, preds)

        results.append({"year": test_year, "mae": mae, "rho": rho, "n": len(test)})

    if not results:
        return 999, 0, []

    avg_mae = np.mean([r["mae"] for r in results])
    avg_rho = np.mean([r["rho"] for r in results])
    return avg_mae, avg_rho, results


def _coarse_search(
    pos_data: pd.DataFrame,
    feature_cols: list[str],
    pos: str,
) -> list[TuneResult]:
    """Coarse grid search over key param combinations.

    Instead of full grid (3*4*3*3*3*3 = 972 combos), do staged search:
    1. Search depth + learning_rate + n_estimators (36 combos)
    2. Fix those, search subsample + colsample + min_child_weight (27 combos)
    """
    print(f"\n  Stage 1: depth / lr / n_estimators (36 combos)...")

    stage1_results = []
    for depth, lr, n_est in itertools.product(
        PARAM_GRID["max_depth"],
        PARAM_GRID["learning_rate"],
        PARAM_GRID["n_estimators"],
    ):
        params = {
            "max_depth": depth,
            "learning_rate": lr,
            "n_estimators": n_est,
            "min_child_weight": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        }
        avg_mae, avg_rho, details = _evaluate_params(
            pos_data, feature_cols, params, TUNE_YEARS
        )
        stage1_results.append(TuneResult(pos, params, avg_mae, avg_rho, details))

    stage1_results.sort(key=lambda r: r.avg_mae)
    best_s1 = stage1_results[0]
    print(f"  Best stage 1: depth={best_s1.params['max_depth']} "
          f"lr={best_s1.params['learning_rate']} "
          f"n_est={best_s1.params['n_estimators']} "
          f"MAE={best_s1.avg_mae:.3f}")

    print(f"  Stage 2: subsample / colsample / min_child_weight (27 combos)...")

    stage2_results = []
    for sub, col, mcw in itertools.product(
        PARAM_GRID["subsample"],
        PARAM_GRID["colsample_bytree"],
        PARAM_GRID["min_child_weight"],
    ):
        params = {
            "max_depth": best_s1.params["max_depth"],
            "learning_rate": best_s1.params["learning_rate"],
            "n_estimators": best_s1.params["n_estimators"],
            "min_child_weight": mcw,
            "subsample": sub,
            "colsample_bytree": col,
        }
        avg_mae, avg_rho, details = _evaluate_params(
            pos_data, feature_cols, params, TUNE_YEARS
        )
        stage2_results.append(TuneResult(pos, params, avg_mae, avg_rho, details))

    stage2_results.sort(key=lambda r: r.avg_mae)
    return stage2_results


def tune_all(force: bool = False) -> dict[str, dict]:
    """Find optimal hyperparameters per position.

    Returns dict of {position: best_params}.
    """
    print("Loading training data...")
    data = build_training_data(force=force)
    feature_cols = get_feature_cols(data)

    print(f"Tuning years: {TUNE_YEARS}")
    print(f"Holdout years: {HOLDOUT_YEARS}")
    print(f"Features: {len(feature_cols)}")

    best_params = {}
    current_params = {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
    }

    for pos in POSITIONS:
        print(f"\n{'='*60}")
        print(f"  TUNING {pos}")
        print(f"{'='*60}")

        pos_data = data[data["position"] == pos].copy()

        # Current baseline
        curr_mae, curr_rho, _ = _evaluate_params(
            pos_data, feature_cols, current_params, TUNE_YEARS
        )
        print(f"  Current params MAE={curr_mae:.3f} rho={curr_rho:.3f}")

        # Search
        results = _coarse_search(pos_data, feature_cols, pos)
        best = results[0]

        print(f"\n  Best found: MAE={best.avg_mae:.3f} rho={best.avg_rho:.3f}")
        print(f"  Params: {best.params}")
        print(f"  Improvement: {(1 - best.avg_mae/curr_mae)*100:+.1f}% MAE")

        # Validate on holdout years
        holdout_mae, holdout_rho, holdout_details = _evaluate_params(
            pos_data, feature_cols, best.params, HOLDOUT_YEARS
        )
        curr_holdout_mae, curr_holdout_rho, _ = _evaluate_params(
            pos_data, feature_cols, current_params, HOLDOUT_YEARS
        )

        print(f"\n  Holdout validation ({HOLDOUT_YEARS}):")
        print(f"    Current:  MAE={curr_holdout_mae:.3f} rho={curr_holdout_rho:.3f}")
        print(f"    Tuned:    MAE={holdout_mae:.3f} rho={holdout_rho:.3f}")
        for d in holdout_details:
            print(f"      {d['year']}: MAE={d['mae']:.3f} rho={d['rho']:.3f} (n={d['n']})")

        # Only keep tuned params if they also improve on holdout
        if holdout_mae < curr_holdout_mae:
            print(f"  >> ACCEPTED (holdout improved by {(1-holdout_mae/curr_holdout_mae)*100:.1f}%)")
            best_params[pos] = best.params
        else:
            print(f"  >> REJECTED (holdout got worse, keeping current params)")
            best_params[pos] = current_params

    # --- Final summary ---
    print(f"\n{'='*60}")
    print("  FINAL TUNED PARAMETERS")
    print(f"{'='*60}")
    for pos in POSITIONS:
        p = best_params[pos]
        print(f"\n  {pos}:")
        for k, v in sorted(p.items()):
            print(f"    {k}: {v}")

    return best_params


if __name__ == "__main__":
    tune_all(force=False)
