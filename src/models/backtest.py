"""Historical backtest comparing our model vs naive baselines.

For each target season in BACKTEST_TARGET_YEARS (the season being predicted),
we run walk-forward: train on all data strictly before that season, predict
every player, then measure how close we got vs the actual PPG they posted.

Three forecasters are compared:

1. Our Model — XGBoost + Bayesian blending (src.models.bayesian._run_one_year)
2. Naive — predict target_ppg = player's PPG in the most recent season
3. Weighted History — exponentially weighted average of a player's last 3
   seasons, regressed toward the position mean based on sample size.

For each (forecaster, position, target_year) we compute MAE, RMSE, R², and
Spearman rank correlation. Results are saved to export/backtest.json so the
API can serve them without re-running the pipeline.

We don't have historical FantasyPros ECR snapshots via nflreadpy (only the
current-season consensus), so we can't backtest against expert consensus.
That comparison lives in consensus_snapshot.py as a current-year snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.pipeline.features import build_feature_matrix
from src.pipeline.targets import build_training_data
from src.models.bayesian import (
    _build_player_history,
    _get_position_priors,
    _learn_calibration_scale,
    _run_one_year,
)
from src.models.xgb import get_feature_cols, POSITIONS

EXPORT_DIR = Path(__file__).resolve().parents[2] / "export"

# Target seasons we want to evaluate (the NFL season being predicted).
# For target_year = 2025, we use feature rows where season == 2024 (shift
# of 1 since target_ppg = next-season ppg).
BACKTEST_TARGET_YEARS = [2021, 2022, 2023, 2024, 2025]


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE, RMSE, R², Spearman rho for one forecaster on one slice."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rho = float(spearmanr(y_true, y_pred).statistic) if len(y_true) > 2 else 0.0

    return {
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "r2": round(r2, 3),
        "spearman": round(rho, 3),
        "n": int(len(y_true)),
    }


def _weighted_history_prediction(
    player_id: str,
    feature_season: int,
    all_features: pd.DataFrame,
    pos_mean: float,
) -> float:
    """Predict next-season PPG from a weighted average of prior seasons.

    Uses exponential weights (most recent season counts 3x, two back 2x,
    three back 1x) and shrinks toward the position mean when the player
    has < 3 seasons of data. A 1st-year player with 1 season gets weight
    0.33 on self, 0.67 on position mean.
    """
    history = all_features[
        (all_features["player_id"] == player_id)
        & (all_features["season"] <= feature_season)
    ].sort_values("season")

    if len(history) == 0:
        return pos_mean

    ppg_vals = history["ppg"].values[-3:]
    weights = np.array([1, 2, 3])[-len(ppg_vals):]
    weighted = float(np.average(ppg_vals, weights=weights))

    # Shrink toward position mean based on sample size
    shrink = len(ppg_vals) / (len(ppg_vals) + 2)
    return shrink * weighted + (1 - shrink) * pos_mean


def run_backtest() -> dict:
    """Run the full 5-year walk-forward backtest across all forecasters."""
    print("Loading training data...")
    data = build_training_data(force=False)
    all_features = build_feature_matrix(force=False)
    feature_cols = get_feature_cols(data)

    print("Building player history priors...")
    history = _build_player_history(all_features)
    position_priors = _get_position_priors(all_features)
    pos_means = {pos: position_priors[pos][0] for pos in POSITIONS}

    per_year_rows: list[dict] = []
    per_position_preds: dict[str, list[dict]] = {pos: [] for pos in POSITIONS}

    for pos in POSITIONS:
        print(f"\n{'='*60}\n  {pos}\n{'='*60}")
        pos_data = data[data["position"] == pos].copy()
        pos_prior_mean, pos_prior_std = position_priors[pos]

        cal_scale = _learn_calibration_scale(
            pos_data, feature_cols, history, pos_prior_mean, pos_prior_std, pos
        )

        for target_year in BACKTEST_TARGET_YEARS:
            # Feature season = target_year - 1 (training data shifts targets back by 1)
            feature_year = target_year - 1
            test = pos_data[pos_data["season"] == feature_year]
            if len(test) == 0:
                continue

            # --- Our model (XGBoost + Bayesian) ---
            _, bay_preds, _, y_test, _ = _run_one_year(
                pos_data, feature_cols, history,
                pos_prior_mean, pos_prior_std, feature_year, pos,
            )

            # --- Naive: predict next year = this year's ppg ---
            naive_preds = test["ppg"].values

            # --- Weighted history ---
            wh_preds = np.array([
                _weighted_history_prediction(
                    pid, feature_year, all_features, pos_means[pos]
                )
                for pid in test["player_id"].values
            ])

            per_year_rows.append({
                "position": pos,
                "target_year": target_year,
                "model": _metrics(y_test, bay_preds),
                "naive": _metrics(y_test, naive_preds),
                "weighted_history": _metrics(y_test, wh_preds),
            })

            print(
                f"  {target_year}: n={len(test):3d} | "
                f"Model MAE={_metrics(y_test, bay_preds)['mae']:.2f}  "
                f"Naive MAE={_metrics(y_test, naive_preds)['mae']:.2f}  "
                f"WHist MAE={_metrics(y_test, wh_preds)['mae']:.2f}"
            )

            # Accumulate for per-position overall metrics
            for pred, name in [
                (bay_preds, "model"),
                (naive_preds, "naive"),
                (wh_preds, "weighted_history"),
            ]:
                for yt, yp in zip(y_test, pred):
                    per_position_preds[pos].append({
                        "forecaster": name,
                        "target_year": target_year,
                        "actual": float(yt),
                        "pred": float(yp),
                    })

    # --- Aggregate per position across all years ---
    per_position_overall: dict[str, dict] = {}
    for pos in POSITIONS:
        rows = per_position_preds[pos]
        if not rows:
            continue
        per_position_overall[pos] = {}
        for forecaster in ("model", "naive", "weighted_history"):
            subset = [r for r in rows if r["forecaster"] == forecaster]
            y_true = np.array([r["actual"] for r in subset])
            y_pred = np.array([r["pred"] for r in subset])
            per_position_overall[pos][forecaster] = _metrics(y_true, y_pred)

    # --- Aggregate overall across all positions and years ---
    overall: dict[str, dict] = {}
    for forecaster in ("model", "naive", "weighted_history"):
        y_true, y_pred = [], []
        for pos in POSITIONS:
            for r in per_position_preds[pos]:
                if r["forecaster"] == forecaster:
                    y_true.append(r["actual"])
                    y_pred.append(r["pred"])
        overall[forecaster] = _metrics(np.array(y_true), np.array(y_pred))

    result = {
        "target_years": BACKTEST_TARGET_YEARS,
        "forecasters": {
            "model": "XGBoost + Bayesian blending (our approach)",
            "naive": "Predict target = player's most recent season PPG",
            "weighted_history": "Exponentially-weighted 3yr history, shrunk to position mean",
        },
        "per_year": per_year_rows,
        "per_position": per_position_overall,
        "overall": overall,
    }

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORT_DIR / "backtest.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved backtest to {out_path}")

    # --- Print summary ---
    print(f"\n{'='*60}\n  OVERALL SUMMARY ({BACKTEST_TARGET_YEARS[0]}-{BACKTEST_TARGET_YEARS[-1]})\n{'='*60}")
    print(f"  {'Forecaster':<20} {'MAE':>6} {'RMSE':>6} {'R²':>6} {'rho':>6}")
    for fc, m in overall.items():
        print(f"  {fc:<20} {m['mae']:>6.2f} {m['rmse']:>6.2f} {m['r2']:>6.3f} {m['spearman']:>6.3f}")

    print(f"\n{'='*60}\n  PER POSITION\n{'='*60}")
    for pos in POSITIONS:
        if pos not in per_position_overall:
            continue
        print(f"\n  {pos}:")
        print(f"  {'Forecaster':<20} {'MAE':>6} {'RMSE':>6} {'R²':>6} {'rho':>6}")
        for fc in ("model", "naive", "weighted_history"):
            m = per_position_overall[pos][fc]
            print(f"  {fc:<20} {m['mae']:>6.2f} {m['rmse']:>6.2f} {m['r2']:>6.3f} {m['spearman']:>6.3f}")

    return result


if __name__ == "__main__":
    run_backtest()
