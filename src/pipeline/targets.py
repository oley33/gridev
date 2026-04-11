"""Build target labels for model training.

The target is: next season's full PPR fantasy points.
Each row in the feature matrix for season N gets paired with the player's
fantasy points from season N+1 (if they played).
"""

from pathlib import Path

import pandas as pd

from src.pipeline.features import build_feature_matrix

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


def build_training_data(force: bool = False) -> pd.DataFrame:
    """Join feature matrix with next-season fantasy points as the target.

    Returns the feature matrix with an added 'target_ppg' column
    (next season's PPR points per game) and 'target_total_pts'
    (next season's total PPR points).

    Rows where the player didn't play the following season are dropped.
    """
    cache_path = CACHE_DIR / "training_data.parquet"
    if cache_path.exists() and not force:
        print("Loading cached training data")
        return pd.read_parquet(cache_path)

    print("Building training data...")
    features = build_feature_matrix(force=force)

    # Build the target: next season's fantasy output
    next_season = features[["player_id", "season", "fantasy_points_ppr_calc", "ppg", "games"]].copy()
    next_season = next_season.rename(columns={
        "fantasy_points_ppr_calc": "target_total_pts",
        "ppg": "target_ppg",
        "games": "target_games",
    })
    next_season["season"] = next_season["season"] - 1  # shift back to align

    # Join: features from season N + target from season N+1
    training = features.merge(
        next_season[["player_id", "season", "target_total_pts", "target_ppg", "target_games"]],
        on=["player_id", "season"],
        how="inner",  # drop players who didn't play the following year
    )

    # Drop rows where target season had very few games (injured early)
    training = training[training["target_games"] >= 4].reset_index(drop=True)

    print(f"Training data: {len(training)} rows")
    print(f"  Seasons: {training['season'].min()}–{training['season'].max()}")
    print(f"  Positions: {training['position'].value_counts().to_dict()}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    training.to_parquet(cache_path, index=False)
    print(f"Cached to {cache_path}")

    return training


if __name__ == "__main__":
    df = build_training_data(force=True)
    print("\nShape:", df.shape)
    print("\nTarget stats:")
    print(df.groupby("position")["target_ppg"].describe().round(1))
