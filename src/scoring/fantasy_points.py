"""Full PPR fantasy points calculation.

Single source of truth for scoring across the entire codebase.
"""

import pandas as pd

# Full PPR scoring weights
SCORING = {
    "passing_yards": 0.04,
    "passing_tds": 4.0,
    "interceptions": -1.0,
    "rushing_yards": 0.1,
    "rushing_tds": 6.0,
    "receptions": 1.0,
    "receiving_yards": 0.1,
    "receiving_tds": 6.0,
    "fumbles_lost": -2.0,
}


def calculate_fantasy_points(df: pd.DataFrame) -> pd.Series:
    """Calculate full PPR fantasy points from a DataFrame with stat columns.

    Handles missing columns gracefully (treats them as 0).
    Fumbles lost is computed from rushing_fumbles_lost + receiving_fumbles_lost
    if 'fumbles_lost' column doesn't exist directly.
    """
    points = pd.Series(0.0, index=df.index)

    for col, weight in SCORING.items():
        if col == "fumbles_lost":
            # nfl_data_py splits fumbles by type
            fumbles = (
                df.get("rushing_fumbles_lost", 0).fillna(0)
                + df.get("receiving_fumbles_lost", 0).fillna(0)
                + df.get("sack_fumbles_lost", 0).fillna(0)
            )
            points += fumbles * weight
        elif col in df.columns:
            points += df[col].fillna(0) * weight

    return points
