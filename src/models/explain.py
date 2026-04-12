"""Per-player explainability using XGBoost SHAP contributions.

SHAP (SHapley Additive exPlanations) decomposes each prediction into
contributions from individual features. For each player we surface the
top features pushing their projection up (pros) and down (cons), with
the contribution measured in PPG units.

XGBoost has native support via `pred_contribs=True` on the booster's
predict method — no extra library required.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import xgboost as xgb
from xgboost import XGBRegressor


# --------------------------------------------------------------------------
# Feature display metadata: friendly label + value formatter.
# The dict keeps the raw values interpretable for the end-user (e.g. 0.24
# target_share -> "24% of team targets") so the pros/cons don't just surface
# feature names that only ML engineers can read.
# --------------------------------------------------------------------------

_pct = lambda v: f"{v * 100:.0f}%"
_one = lambda v: f"{v:.1f}"
_int = lambda v: f"{int(v)}"
_share = lambda v: f"{v * 100:.1f}%"


FEATURE_META: dict[str, tuple[str, Callable[[float], str]]] = {
    # Volume
    "pass_att_per_game": ("Pass attempts / game", _one),
    "rush_att_per_game": ("Rush attempts / game", _one),
    "targets_per_game": ("Targets / game", _one),
    "receptions_per_game": ("Receptions / game", _one),
    "receiving_yards_per_game": ("Rec yards / game", _one),
    "rushing_yards_per_game": ("Rush yards / game", _one),
    "target_share_clean": ("Target share", _share),
    "air_yards_share_clean": ("Air yards share", _share),
    "wopr": ("WOPR (opportunity rating)", _one),
    # Efficiency
    "yards_per_carry": ("Yards per carry", _one),
    "yards_per_target": ("Yards per target", _one),
    "catch_rate": ("Catch rate", _pct),
    "yards_per_reception": ("Yards per reception", _one),
    "racr_clean": ("RACR (air yards efficiency)", _one),
    "air_yards_per_target": ("Air yards per target", _one),
    # Scoring
    "total_tds": ("Total TDs", _int),
    "tds_per_game": ("TDs per game", _one),
    "rz_carries": ("Red-zone carries", _int),
    "rz_targets": ("Red-zone targets", _int),
    "rz_opportunities": ("Red-zone touches", _int),
    "rz_rush_share": ("RZ rush share", _share),
    "rz_target_share": ("RZ target share", _share),
    "expected_rz_tds": ("Expected RZ TDs", _one),
    "actual_rz_tds": ("Actual RZ TDs", _int),
    "td_over_expected": ("TDs over expected", _one),
    # EPA
    "passing_epa_clean": ("Passing EPA", _one),
    "rushing_epa_clean": ("Rushing EPA", _one),
    "receiving_epa_clean": ("Receiving EPA", _one),
    # Career
    "age": ("Age", _one),
    "years_exp": ("Years of experience", _int),
    "years_from_peak": ("Years from position peak", _one),
    "avg_snap_pct": ("Snap share", _pct),
    "changed_team": ("Changed team", lambda v: "yes" if v > 0.5 else "no"),
    # Team context
    "team_implied_pts": ("Team implied total", _one),
    "qb_passing_epa": ("QB passing EPA", _one),
    "qb_comp_pct": ("QB completion %", _pct),
    "qb_yards_per_att": ("QB yards per attempt", _one),
    "draft_capital": ("Draft capital", _one),
    # Weekly profile
    "weekly_pts_std": ("Weekly scoring volatility", _one),
    "weekly_pts_median": ("Median weekly score", _one),
    "weekly_cv": ("Weekly coefficient of variation", _one),
    "weeks_played": ("Weeks played", _int),
}


def _label(feature: str) -> str:
    return FEATURE_META.get(feature, (feature, _one))[0]


def _format_value(feature: str, value: float) -> str:
    formatter = FEATURE_META.get(feature, (feature, _one))[1]
    try:
        return formatter(float(value))
    except (TypeError, ValueError):
        return str(value)


def compute_shap_explanations(
    model: XGBRegressor,
    X: np.ndarray,
    feature_cols: list[str],
    top_k: int = 4,
    min_abs_contrib: float = 0.05,
) -> list[dict]:
    """Compute per-row SHAP explanations.

    Returns one dict per row with shape:
        {
          "pros": [{"feature": str, "label": str, "value": str,
                    "value_raw": float, "impact": float}, ...],
          "cons": [...same shape, negative impacts...],
        }

    Impact is in the model's output units (PPG). Positive impact pushes
    the projection up relative to the model's baseline.
    """
    booster = model.get_booster()
    dmatrix = xgb.DMatrix(X, feature_names=feature_cols)
    # Shape (n, k+1) — last column is the expected value / bias term
    contribs = booster.predict(dmatrix, pred_contribs=True)

    n_features = len(feature_cols)
    assert contribs.shape[1] == n_features + 1

    out: list[dict] = []
    for i in range(contribs.shape[0]):
        row_contribs = contribs[i, :n_features]
        row_values = X[i]

        idx_sorted = np.argsort(row_contribs)

        # Cons: most negative contributions
        cons: list[dict] = []
        for j in idx_sorted:
            if row_contribs[j] >= -min_abs_contrib:
                break
            feat = feature_cols[j]
            cons.append({
                "feature": feat,
                "label": _label(feat),
                "value": _format_value(feat, row_values[j]),
                "value_raw": round(float(row_values[j]), 4),
                "impact": round(float(row_contribs[j]), 3),
            })
            if len(cons) >= top_k:
                break

        # Pros: most positive contributions
        pros: list[dict] = []
        for j in idx_sorted[::-1]:
            if row_contribs[j] <= min_abs_contrib:
                break
            feat = feature_cols[j]
            pros.append({
                "feature": feat,
                "label": _label(feat),
                "value": _format_value(feat, row_values[j]),
                "value_raw": round(float(row_values[j]), 4),
                "impact": round(float(row_contribs[j]), 3),
            })
            if len(pros) >= top_k:
                break

        out.append({"pros": pros, "cons": cons})

    return out
