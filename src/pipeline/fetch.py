"""Fetch and cache raw NFL data from nfl_data_py.

Pulls seasonal stats, weekly stats, rosters, snap counts, schedules (Vegas lines),
play-by-play (red zone), and draft picks.
Caches as parquet in data/raw/ to avoid re-downloading on every run.
"""

from pathlib import Path

import nfl_data_py as nfl
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

FIRST_SEASON = 2012
LATEST_SEASON = 2024


def _cache_path(name: str) -> Path:
    return RAW_DIR / f"{name}.parquet"


def _load_or_fetch(name: str, fetch_fn, force: bool = False) -> pd.DataFrame:
    """Load from cache if available, otherwise fetch and save."""
    path = _cache_path(name)
    if path.exists() and not force:
        print(f"  Loading cached {name}")
        return pd.read_parquet(path)

    print(f"  Fetching {name}...")
    df = fetch_fn()

    # Fix mixed-type columns that break parquet serialization.
    # nfl_data_py seasonal data has columns like player_name where the type
    # is inconsistent across rows (concatenated per-game bug).
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).replace("nan", pd.NA)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"  Cached {name} ({len(df)} rows)")
    return df


def fetch_seasonal(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Seasonal (full-season) player stats."""
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))
    return _load_or_fetch(
        "seasonal",
        lambda: nfl.import_seasonal_data(seasons),
        force=force,
    )


def fetch_weekly(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Weekly player stats — used for variance/consistency metrics."""
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))
    return _load_or_fetch(
        "weekly",
        lambda: nfl.import_weekly_data(seasons),
        force=force,
    )


def fetch_rosters(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Rosters — source of truth for position, age, experience."""
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))
    return _load_or_fetch(
        "rosters",
        lambda: nfl.import_rosters(seasons),
        force=force,
    )


def fetch_snap_counts(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Weekly snap counts — used to compute snap share %. Available from 2013."""
    seasons = seasons or list(range(max(FIRST_SEASON, 2013), LATEST_SEASON + 1))
    return _load_or_fetch(
        "snap_counts",
        lambda: nfl.import_snap_counts(seasons),
        force=force,
    )


def fetch_schedules(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Game schedules with Vegas lines (spread, total). Used for implied team totals."""
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))
    return _load_or_fetch(
        "schedules",
        lambda: nfl.import_schedules(seasons),
        force=force,
    )


def fetch_pbp_redzone(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Play-by-play filtered to red zone (yardline_100 <= 20).

    Only fetches columns needed for red zone opportunity and TD analysis.
    """
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))

    pbp_cols = [
        "season", "week", "game_id", "posteam", "play_type", "yardline_100",
        "passer_player_id", "rusher_player_id", "receiver_player_id",
        "td_player_id", "rush_touchdown", "pass_touchdown", "yards_gained",
        "season_type",
    ]

    def _fetch():
        # Pull PBP year-by-year (bulk fetch silently drops years),
        # filter to red zone, and keep only needed columns.
        chunks = []
        for year in seasons:
            try:
                ydf = nfl.import_pbp_data([year])
                ydf = ydf[
                    (ydf["yardline_100"] <= 20)
                    & (ydf["season_type"] == "REG")
                    & (ydf["play_type"].isin(["pass", "run"]))
                ]
                keep = [c for c in pbp_cols if c in ydf.columns]
                chunks.append(ydf[keep])
                print(f"    {year}: {len(ydf)} red zone plays")
            except Exception as e:
                print(f"    {year}: skipped ({e})")
        return pd.concat(chunks, ignore_index=True)

    return _load_or_fetch("pbp_redzone", _fetch, force=force)


def fetch_draft_picks(force: bool = False) -> pd.DataFrame:
    """Historical draft picks — used for draft capital feature."""
    return _load_or_fetch(
        "draft_picks",
        lambda: nfl.import_draft_picks(),
        force=force,
    )


def fetch_all(force: bool = False) -> dict[str, pd.DataFrame]:
    """Fetch all raw datasets. Returns dict keyed by dataset name."""
    print("Fetching all raw data...")
    data = {
        "seasonal": fetch_seasonal(force=force),
        "weekly": fetch_weekly(force=force),
        "rosters": fetch_rosters(force=force),
        "snap_counts": fetch_snap_counts(force=force),
        "schedules": fetch_schedules(force=force),
        "pbp_redzone": fetch_pbp_redzone(force=force),
        "draft_picks": fetch_draft_picks(force=force),
    }
    print("Done.")
    return data


if __name__ == "__main__":
    fetch_all()
