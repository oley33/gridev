"""Train final models on all available data and export projections.

This is the offline step that runs before deployment. It:
1. Trains position-specific XGBoost models on all historical data
2. Applies Bayesian updating and calibration
3. Runs Monte Carlo simulations
4. Serializes models and projections to disk for the API to load
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, skewnorm
from xgboost import XGBRegressor

from src.pipeline.features import build_feature_matrix
from src.pipeline.targets import build_training_data
from src.models.xgb import get_feature_cols, TUNED_PARAMS, FIXED_PARAMS, POSITIONS
from src.models.bayesian import (
    _build_player_history,
    _get_position_priors,
    _estimate_model_std_cv,
    bayesian_update,
    CALIBRATION_YEARS,
)
from src.models.monte_carlo import (
    BOOM_THRESHOLDS,
    BUST_THRESHOLDS,
    N_SIMS,
)
from src.models.explain import compute_shap_explanations
from src.scoring.fantasy_points import SCORING

EXPORT_DIR = Path(__file__).resolve().parents[2] / "export"


def _run_monte_carlo(
    pred_mean: float,
    pred_std: float,
    pos: str,
    rng: np.random.Generator,
    n_sims: int = N_SIMS,
) -> dict:
    """Run Monte Carlo simulation for a single player."""
    skew_by_pos = {"QB": 1.0, "RB": 2.0, "WR": 1.5, "TE": 2.5}
    skew = skew_by_pos.get(pos, 1.5)

    samples = skewnorm.rvs(
        a=skew, loc=pred_mean, scale=pred_std, size=n_sims, random_state=rng
    )
    samples = np.clip(samples, 0, None)
    median_shift = pred_mean - np.median(samples)
    samples = np.clip(samples + median_shift, 0, None)

    return {
        "proj_median": round(float(np.median(samples)), 2),
        "proj_mean": round(float(np.mean(samples)), 2),
        "floor_p10": round(float(np.percentile(samples, 10)), 2),
        "floor_p25": round(float(np.percentile(samples, 25)), 2),
        "ceiling_p75": round(float(np.percentile(samples, 75)), 2),
        "ceiling_p90": round(float(np.percentile(samples, 90)), 2),
        "proj_std": round(float(np.std(samples)), 2),
        "boom_pct": round(float(np.mean(samples >= BOOM_THRESHOLDS[pos])), 3),
        "bust_pct": round(float(np.mean(samples <= BUST_THRESHOLDS[pos])), 3),
    }


def export_projections(target_season: int = 2026, force: bool = False) -> Path:
    """Train on all data up to target_season and export projections.

    The target_season is the season we're projecting (the upcoming draft).
    We train on all data before it and predict target_season performance
    for all players who played in target_season - 1.
    """
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Exporting projections for {target_season} season...")
    print(f"Training on all data through {target_season - 1}")

    # Load data
    features = build_feature_matrix(force=force)
    training = build_training_data(force=force)
    feature_cols = get_feature_cols(training)

    # Player history for Bayesian priors
    history = _build_player_history(features)
    position_priors = _get_position_priors(features)

    # Players to project: those who played in the most recent season available
    # In a real deployment, this would be target_season - 1
    projection_season = target_season - 1
    to_project = features[features["season"] == projection_season].copy()

    print(f"Projecting {len(to_project)} players from {projection_season} season")

    all_projections = []
    exported_models = {}
    rng = np.random.default_rng(42)

    for pos in POSITIONS:
        print(f"\n  {pos}:")

        # Train on all historical training data before target_season
        pos_train = training[
            (training["position"] == pos) & (training["season"] < target_season)
        ]
        pos_project = to_project[to_project["position"] == pos]

        if len(pos_train) == 0 or len(pos_project) == 0:
            print(f"    Skipping — no data")
            continue

        X_train = pos_train[feature_cols].values
        y_train = pos_train["target_ppg"].values

        # Train final model
        model = XGBRegressor(**TUNED_PARAMS[pos], **FIXED_PARAMS)
        model.fit(X_train, y_train)

        # Save model
        model_path = EXPORT_DIR / f"model_{pos.lower()}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        exported_models[pos] = model_path
        print(f"    Model saved to {model_path}")

        # Predict
        X_proj = pos_project[feature_cols].values
        xgb_preds = model.predict(X_proj)

        # SHAP explanations — per-player pros/cons in PPG units
        explanations = compute_shap_explanations(model, X_proj, feature_cols)

        # Model uncertainty via CV
        model_std = _estimate_model_std_cv(model, X_train, y_train)

        # Calibration scale (learned from calibration years)
        cal_z_scores = []
        for cal_year in CALIBRATION_YEARS:
            cal_train = pos_train[pos_train["season"] < cal_year]
            cal_test = pos_train[pos_train["season"] == cal_year]
            if len(cal_train) < 10 or len(cal_test) < 5:
                continue
            cal_model = XGBRegressor(**TUNED_PARAMS[pos], **FIXED_PARAMS)
            cal_model.fit(cal_train[feature_cols].values, cal_train["target_ppg"].values)
            cal_preds = cal_model.predict(cal_test[feature_cols].values)
            cal_residuals = cal_test["target_ppg"].values - cal_preds
            cal_z_scores.extend((cal_residuals / model_std).tolist())

        cal_scale = np.std(cal_z_scores) if len(cal_z_scores) >= 10 else 1.5

        # Bayesian update + Monte Carlo for each player
        pos_prior_mean, pos_prior_std = position_priors[pos]
        proj_history = pos_project.merge(
            history, on=["player_id", "season"], how="left"
        )

        # Skew parameter used in Monte Carlo (must match _run_monte_carlo)
        skew_by_pos = {"QB": 1.0, "RB": 2.0, "WR": 1.5, "TE": 2.5}
        pos_skew = skew_by_pos.get(pos, 1.5)

        pos_projections = []
        pos_dist_params = []  # (bay_pred, bay_std) kept for relative-bust second pass

        for i, (xgb_pred, row) in enumerate(
            zip(xgb_preds, proj_history.itertuples())
        ):
            p_mean = row.prior_mean if pd.notna(row.prior_mean) else pos_prior_mean
            p_std = row.prior_std if pd.notna(row.prior_std) else pos_prior_std
            n_seasons = row.n_prior_seasons if pd.notna(row.n_prior_seasons) else 0
            p_std = max(p_std if not np.isnan(p_std) else pos_prior_std, 1.5)

            if n_seasons == 0:
                bay_pred = xgb_pred
                bay_std = model_std * 1.2 * cal_scale
            else:
                blend_weight = 0.85
                bay_pred = blend_weight * xgb_pred + (1 - blend_weight) * p_mean
                history_shrink = 1.0 / (1.0 + 0.15 * n_seasons)
                player_std = model_std * max(history_shrink, 0.7)
                volatility_boost = min(p_std / pos_prior_std, 2.0)
                player_std *= volatility_boost
                bay_std = player_std * cal_scale

            mc = _run_monte_carlo(bay_pred, bay_std, pos, rng)

            player_row = pos_project.iloc[i]
            projection = {
                "player_id": str(player_row["player_id"]),
                "player_name": str(player_row["player_display_name"]),
                "position": pos,
                "team": str(player_row["team"]),
                "season": int(target_season),
                "age": round(float(player_row["age"]), 1) if pd.notna(player_row["age"]) else None,
                "games_prev": int(player_row["games"]),
                "ppg_prev": round(float(player_row["ppg"]), 2),
                **mc,
                "explanation": explanations[i],
            }
            pos_projections.append(projection)
            # Store post-MC std (the actual simulated spread) for relative bust calc.
            # This is wider and more honest than bay_std for established veterans.
            pos_dist_params.append(mc["proj_std"])

        # --- Relative bust: rank-adjusted disappointment probability ---
        # Sort within position by proj_median so we can compute thresholds.
        # For the player projected at rank R, bust = P(their PPG falls below
        # the projection of the player currently at rank R + BUST_FALLOFF).
        # This means a rank-1 pick needs to stay near the top to avoid "bust"
        # territory, while a late-round pick just needs to not crater.
        BUST_FALLOFF = 12  # "falls a full positional tier"

        sorted_idx = sorted(
            range(len(pos_projections)),
            key=lambda k: pos_projections[k]["proj_median"],
            reverse=True,
        )
        pos_projections = [pos_projections[k] for k in sorted_idx]
        pos_dist_params = [pos_dist_params[k] for k in sorted_idx]
        n_pos = len(pos_projections)

        for rank_i, (proj, proj_std) in enumerate(
            zip(pos_projections, pos_dist_params)
        ):
            threshold_rank_i = min(rank_i + BUST_FALLOFF, n_pos - 1)
            threshold_ppg = pos_projections[threshold_rank_i]["proj_median"]

            # Use the simulated proj_std (post-MC spread) for the CDF.
            # Floor it at 2.0 PPG — even a perfectly predictable player has
            # genuine season-level variance from injury, game-script, etc.
            effective_std = max(proj_std, 2.0)
            # Normal approximation: proj_median is already the median of the
            # simulation, so this is consistent with the displayed floor/ceiling.
            rel_bust = float(norm.cdf(threshold_ppg, loc=proj["proj_median"], scale=effective_std))
            rel_bust = round(float(np.clip(rel_bust, 0.0, 1.0)), 3)

            proj["pos_rank"] = rank_i + 1
            proj["relative_bust_pct"] = rel_bust
            proj["bust_threshold_rank"] = threshold_rank_i + 1
            proj["bust_threshold_ppg"] = round(float(threshold_ppg), 2)

        all_projections.extend(pos_projections)
        print(f"    {len(pos_projections)} players projected")

    # Sort by projected median descending
    all_projections.sort(key=lambda p: p["proj_median"], reverse=True)

    # Save projections as JSON
    projections_path = EXPORT_DIR / f"projections_{target_season}.json"
    with open(projections_path, "w") as f:
        json.dump(all_projections, f, indent=2)
    print(f"\nProjections saved to {projections_path}")
    print(f"Total players: {len(all_projections)}")

    # Save metadata
    meta = {
        "target_season": target_season,
        "training_seasons": f"2012-{target_season - 1}",
        "n_players": len(all_projections),
        "positions": {pos: len([p for p in all_projections if p["position"] == pos]) for pos in POSITIONS},
        "feature_cols": feature_cols,
        "scoring": SCORING,
        "boom_thresholds": BOOM_THRESHOLDS,
        "bust_thresholds": BUST_THRESHOLDS,
    }
    meta_path = EXPORT_DIR / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return projections_path


if __name__ == "__main__":
    export_projections(target_season=2026, force=False)
