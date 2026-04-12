"""Fetch and cache raw NFL data from nflreadpy.

Pulls seasonal stats, weekly stats, rosters, snap counts, schedules (Vegas lines),
play-by-play (red zone), and draft picks.
Caches as parquet in data/raw/ to avoid re-downloading on every run.

Note: we migrated from nfl_data_py (deprecated Sep 2025) to nflreadpy.
nflreadpy returns polars DataFrames by default, which we convert to pandas
to keep the rest of the pipeline unchanged. We also aggregate weekly stats
to seasonal ourselves, since nflreadpy removed the pre-aggregated endpoint.
"""

from pathlib import Path

import nflreadpy as nfl
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

FIRST_SEASON = 2012
LATEST_SEASON = 2025


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
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).replace("nan", pd.NA)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"  Cached {name} ({len(df)} rows)")
    return df


def _to_pandas(df) -> pd.DataFrame:
    """Convert polars DataFrame to pandas if needed."""
    if hasattr(df, "to_pandas"):
        return df.to_pandas()
    return df


def _aggregate_weekly_to_seasonal(weekly: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly stats to season totals.

    nflreadpy removed the pre-aggregated seasonal endpoint. We sum stat columns
    and keep the most common value for metadata columns (position, team, etc.).
    """
    # Regular season only - matches nfl_data_py's seasonal default
    reg = weekly[weekly["season_type"] == "REG"].copy()

    # Metadata: take first non-null per player-season
    meta_cols = [
        "player_name", "player_display_name", "position", "position_group",
        "headshot_url",
    ]
    meta_cols = [c for c in meta_cols if c in reg.columns]

    # Stat columns: sum across weeks. Share/rate columns: mean across weeks.
    exclude = set(meta_cols) | {
        "player_id", "season", "week", "season_type", "team", "opponent_team",
    }
    # These are weekly rates/shares, not counting stats — averaging preserves meaning.
    rate_cols = {
        "target_share", "air_yards_share", "wopr", "racr", "pacr", "dakota",
        "passing_epa", "rushing_epa", "receiving_epa", "passing_cpoe",
    }
    numeric_cols = [
        c for c in reg.columns
        if c not in exclude and pd.api.types.is_numeric_dtype(reg[c])
    ]

    # Games played = count of weeks with any record
    agg_dict = {}
    for c in numeric_cols:
        agg_dict[c] = "mean" if c in rate_cols else "sum"
    for c in meta_cols:
        agg_dict[c] = "first"

    grouped = reg.groupby(["player_id", "season"], as_index=False).agg(agg_dict)
    grouped["games"] = (
        reg.groupby(["player_id", "season"]).size().reset_index(name="games")["games"]
    )

    # Rename columns to match the old nfl_data_py seasonal schema used downstream
    rename = {
        "passing_interceptions": "interceptions",
        "sacks_suffered": "sacks",
        "sack_yards_lost": "sack_yards",
    }
    grouped = grouped.rename(columns={k: v for k, v in rename.items() if k in grouped.columns})

    return grouped


def fetch_weekly(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Weekly player stats — used for variance/consistency metrics."""
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))

    def _fetch():
        df = _to_pandas(nfl.load_player_stats(seasons=seasons))
        # Rename for compatibility with old pipeline
        rename = {
            "passing_interceptions": "interceptions",
            "sacks_suffered": "sacks",
            "sack_yards_lost": "sack_yards",
        }
        df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
        return df

    return _load_or_fetch("weekly", _fetch, force=force)


def fetch_seasonal(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Seasonal (full-season) player stats. Aggregated from weekly data."""
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))

    def _fetch():
        weekly = _to_pandas(nfl.load_player_stats(seasons=seasons))
        return _aggregate_weekly_to_seasonal(weekly)

    return _load_or_fetch("seasonal", _fetch, force=force)


def fetch_rosters(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Rosters — source of truth for position, age, experience.

    nflreadpy uses `gsis_id` and `full_name`; we rename to `player_id`/`player_name`
    to match the schema the rest of the pipeline expects.
    """
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))

    def _fetch():
        df = _to_pandas(nfl.load_rosters(seasons=seasons))
        df = df.rename(columns={"gsis_id": "player_id", "full_name": "player_name"})
        return df

    return _load_or_fetch("rosters", _fetch, force=force)


def fetch_snap_counts(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Weekly snap counts — used to compute snap share %. Available from 2013."""
    seasons = seasons or list(range(max(FIRST_SEASON, 2013), LATEST_SEASON + 1))
    return _load_or_fetch(
        "snap_counts",
        lambda: _to_pandas(nfl.load_snap_counts(seasons=seasons)),
        force=force,
    )


def fetch_schedules(seasons: list[int] | None = None, force: bool = False) -> pd.DataFrame:
    """Game schedules with Vegas lines (spread, total). Used for implied team totals."""
    seasons = seasons or list(range(FIRST_SEASON, LATEST_SEASON + 1))
    return _load_or_fetch(
        "schedules",
        lambda: _to_pandas(nfl.load_schedules(seasons=seasons)),
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
        # Pull PBP year-by-year to recover from occasional per-year failures.
        chunks = []
        for year in seasons:
            try:
                ydf = _to_pandas(nfl.load_pbp(seasons=[year]))
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
    """Historical draft picks — used for draft capital feature.

    nflreadpy uses `gsis_id`; rename to `player_id` to match old schema.
    """
    def _fetch():
        df = _to_pandas(nfl.load_draft_picks())
        df = df.rename(columns={"gsis_id": "player_id"})
        return df

    return _load_or_fetch("draft_picks", _fetch, force=force)


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
