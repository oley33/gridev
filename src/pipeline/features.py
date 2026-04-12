"""Build the per-player-per-season feature matrix.

Takes raw data from fetch.py and produces one row per player-season with
all engineered features ready for model training.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.pipeline.fetch import fetch_all
from src.scoring.fantasy_points import calculate_fantasy_points

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
POSITIONS = ["QB", "RB", "WR", "TE"]


def _clean_position(rosters: pd.DataFrame) -> pd.DataFrame:
    """Get canonical position per player-season from rosters.

    The seasonal data has a bug where position is concatenated per game,
    so we always source position from rosters instead.
    """
    pos = (
        rosters[rosters["position"].isin(POSITIONS)]
        .groupby(["player_id", "season"])["position"]
        .first()
        .reset_index()
    )
    return pos


def _get_player_teams(rosters: pd.DataFrame) -> pd.DataFrame:
    """Get player -> team mapping per season from rosters."""
    return (
        rosters[["player_id", "season", "team"]]
        .drop_duplicates(subset=["player_id", "season"])
    )


def _compute_snap_pct(
    snap_counts: pd.DataFrame, rosters: pd.DataFrame
) -> pd.DataFrame:
    """Aggregate weekly snap counts to season-level snap share.

    Snap counts use pfr_player_id; we join through rosters (pfr_id) to get player_id.
    """
    # Build pfr_id -> player_id mapping from rosters
    id_map = (
        rosters[["player_id", "pfr_id", "season"]]
        .dropna(subset=["pfr_id"])
        .drop_duplicates(subset=["pfr_id", "season"])
    )

    # Filter to offensive snaps, regular season
    snaps = snap_counts[snap_counts["game_type"] == "REG"].copy()
    snaps = snaps[snaps["offense_pct"].notna() & (snaps["offense_pct"] > 0)]

    season_snaps = (
        snaps.groupby(["pfr_player_id", "season"])
        .agg(
            total_off_snaps=("offense_snaps", "sum"),
            games_with_snaps=("offense_snaps", "count"),
            avg_snap_pct=("offense_pct", "mean"),
        )
        .reset_index()
    )

    # Join to get player_id
    season_snaps = season_snaps.merge(
        id_map,
        left_on=["pfr_player_id", "season"],
        right_on=["pfr_id", "season"],
        how="inner",
    )

    return season_snaps[["player_id", "season", "total_off_snaps", "games_with_snaps", "avg_snap_pct"]]


def _compute_weekly_consistency(weekly: pd.DataFrame) -> pd.DataFrame:
    """Compute week-to-week consistency metrics from weekly data."""
    weekly = weekly[weekly["season_type"] == "REG"].copy()
    weekly["fantasy_points_ppr_calc"] = calculate_fantasy_points(weekly)

    consistency = (
        weekly.groupby(["player_id", "season"])
        .agg(
            weekly_pts_std=("fantasy_points_ppr_calc", "std"),
            weekly_pts_median=("fantasy_points_ppr_calc", "median"),
            weeks_played=("fantasy_points_ppr_calc", "count"),
        )
        .reset_index()
    )
    # Coefficient of variation — normalized consistency measure
    consistency["weekly_cv"] = (
        consistency["weekly_pts_std"] / consistency["weekly_pts_median"].clip(lower=1.0)
    )
    return consistency


def _compute_age(rosters: pd.DataFrame) -> pd.DataFrame:
    """Compute player age at start of each season."""
    roster_cols = rosters[["player_id", "season", "birth_date", "years_exp"]].copy()
    roster_cols = roster_cols.drop_duplicates(subset=["player_id", "season"])

    roster_cols["birth_date"] = pd.to_datetime(roster_cols["birth_date"], errors="coerce")
    # Age at Sept 1 of the season
    roster_cols["age"] = roster_cols.apply(
        lambda r: (pd.Timestamp(f"{r['season']}-09-01") - r["birth_date"]).days / 365.25
        if pd.notna(r["birth_date"])
        else np.nan,
        axis=1,
    )
    return roster_cols[["player_id", "season", "age", "years_exp"]]


def _compute_team_change(rosters: pd.DataFrame) -> pd.DataFrame:
    """Flag players who changed teams between seasons."""
    player_teams = _get_player_teams(rosters)

    # Self-join: compare this season's team to last season's team
    prev = player_teams.copy()
    prev["season"] = prev["season"] + 1
    prev = prev.rename(columns={"team": "prev_team"})

    merged = player_teams.merge(prev, on=["player_id", "season"], how="left")
    merged["changed_team"] = (
        merged["prev_team"].notna()
        & (merged["team"] != merged["prev_team"])
    ).astype(int)

    return merged[["player_id", "season", "changed_team"]]


def _compute_vegas_implied_totals(schedules: pd.DataFrame) -> pd.DataFrame:
    """Compute season-average Vegas implied team total per team.

    Implied total = (game total_line / 2) adjusted by spread.
    Home team implied = (total_line / 2) - (spread_line / 2)
    Away team implied = (total_line / 2) + (spread_line / 2)
    (spread_line is from the home team's perspective, negative = home favored)
    """
    sched = schedules[
        (schedules["game_type"] == "REG")
        & schedules["total_line"].notna()
        & schedules["spread_line"].notna()
    ].copy()

    # Home team implied points
    home = sched[["season", "home_team", "total_line", "spread_line"]].copy()
    home["implied_total"] = (home["total_line"] / 2) - (home["spread_line"] / 2)
    home = home.rename(columns={"home_team": "team"})

    # Away team implied points
    away = sched[["season", "away_team", "total_line", "spread_line"]].copy()
    away["implied_total"] = (away["total_line"] / 2) + (away["spread_line"] / 2)
    away = away.rename(columns={"away_team": "team"})

    all_games = pd.concat([home[["season", "team", "implied_total"]],
                           away[["season", "team", "implied_total"]]])

    # Season average per team
    team_implied = (
        all_games.groupby(["team", "season"])["implied_total"]
        .mean()
        .reset_index()
        .rename(columns={"implied_total": "team_implied_pts"})
    )

    return team_implied


def _compute_redzone_stats(pbp_redzone: pd.DataFrame) -> pd.DataFrame:
    """Compute red zone opportunity share and expected TDs per player-season.

    Red zone = plays where yardline_100 <= 20.
    """
    rz = pbp_redzone.copy()

    # --- Red zone rushing opportunities ---
    rz_rush = rz[rz["play_type"] == "run"].copy()
    rush_player = (
        rz_rush.groupby(["rusher_player_id", "season"])
        .agg(
            rz_carries=("play_type", "count"),
            rz_rush_tds=("rush_touchdown", "sum"),
        )
        .reset_index()
        .rename(columns={"rusher_player_id": "player_id"})
    )

    # Team red zone rush totals for share calc
    rz_rush_team = (
        rz_rush.groupby(["posteam", "season"])["play_type"]
        .count()
        .reset_index()
        .rename(columns={"posteam": "team", "play_type": "team_rz_carries"})
    )

    # --- Red zone receiving opportunities ---
    rz_pass = rz[rz["play_type"] == "pass"].copy()
    recv_player = (
        rz_pass.groupby(["receiver_player_id", "season"])
        .agg(
            rz_targets=("play_type", "count"),
            rz_rec_tds=("pass_touchdown", "sum"),
        )
        .reset_index()
        .rename(columns={"receiver_player_id": "player_id"})
    )

    # Team red zone pass totals for share calc
    rz_pass_team = (
        rz_pass.groupby(["posteam", "season"])["play_type"]
        .count()
        .reset_index()
        .rename(columns={"posteam": "team", "play_type": "team_rz_targets"})
    )

    return rush_player, recv_player, rz_rush_team, rz_pass_team


def _compute_qb_quality(seasonal: pd.DataFrame, rosters: pd.DataFrame) -> pd.DataFrame:
    """Compute QB quality metrics per team-season.

    For each team, find the primary QB (most pass attempts) and use their
    EPA and completion stats as a feature for all skill position players on that team.
    """
    # Get positions from rosters
    positions = _clean_position(rosters)
    player_teams = _get_player_teams(rosters)

    # Drop bugged position columns from seasonal before merging clean ones
    seasonal_clean = seasonal.drop(columns=["position", "position_group"], errors="ignore")
    seasonal_pos = seasonal_clean.merge(positions, on=["player_id", "season"], how="inner")
    seasonal_pos = seasonal_pos.merge(player_teams, on=["player_id", "season"], how="left")

    # Filter to QBs with meaningful attempts
    qbs = seasonal_pos[
        (seasonal_pos["position"] == "QB") & (seasonal_pos["attempts"].fillna(0) > 100)
    ].copy()

    # For each team-season, take the QB with the most attempts
    qbs["attempts_filled"] = qbs["attempts"].fillna(0)
    idx = qbs.groupby(["team", "season"])["attempts_filled"].idxmax()
    primary_qbs = qbs.loc[idx].copy()

    qb_quality = primary_qbs[["team", "season"]].copy()
    qb_quality["qb_passing_epa"] = primary_qbs["passing_epa"].values
    qb_quality["qb_comp_pct"] = (
        primary_qbs["completions"].fillna(0).values
        / primary_qbs["attempts"].fillna(1).clip(lower=1).values
    )
    qb_quality["qb_yards_per_att"] = (
        primary_qbs["passing_yards"].fillna(0).values
        / primary_qbs["attempts"].fillna(1).clip(lower=1).values
    )

    return qb_quality


def _compute_draft_capital(draft_picks: pd.DataFrame) -> pd.DataFrame:
    """Map draft pick to a capital value for each player.

    Higher draft picks = more capital = more likely to get opportunity.
    Uses gsis_id to join to player_id. Value decays — only relevant
    for first ~4 years of career.
    """
    picks = draft_picks[draft_picks["player_id"].notna()].copy()
    picks = picks[["player_id", "season", "pick"]].rename(
        columns={"season": "draft_season", "pick": "draft_pick"}
    )
    # Invert: pick 1 = highest capital. Cap at 260 (total picks).
    picks["draft_capital"] = (261 - picks["draft_pick"]).clip(lower=1) / 260
    return picks[["player_id", "draft_season", "draft_pick", "draft_capital"]]


def build_feature_matrix(force: bool = False) -> pd.DataFrame:
    """Build the complete feature matrix.

    Returns one row per player-season with all features needed for modeling.
    """
    cache_path = CACHE_DIR / "feature_matrix.parquet"
    if cache_path.exists() and not force:
        print("Loading cached feature matrix")
        return pd.read_parquet(cache_path)

    print("Building feature matrix...")
    raw = fetch_all()
    seasonal = raw["seasonal"]
    weekly = raw["weekly"]
    rosters = raw["rosters"]
    snap_counts = raw["snap_counts"]
    schedules = raw["schedules"]
    pbp_redzone = raw["pbp_redzone"]
    draft_picks = raw["draft_picks"]

    # --- 1. Get clean positions, team mappings, and names ---
    positions = _clean_position(rosters)
    player_teams = _get_player_teams(rosters)

    # Clean names from rosters — seasonal player_display_name concatenates per game
    # Use player_name from rosters (already clean), keyed by player_id only since
    # names don't change season to season for the same player
    clean_names = (
        rosters[["player_id", "player_name"]]
        .drop_duplicates(subset=["player_id"])
    )

    # --- 2. Start with seasonal stats, fix position ---
    df = seasonal.copy()
    # Drop bugged columns: position concatenates per game, player_name is also
    # bugged in some versions. Clean names come from rosters below.
    df = df.drop(columns=["position", "position_group", "player_name"], errors="ignore")
    df = df.merge(positions, on=["player_id", "season"], how="inner")
    df = df[df["position"].isin(POSITIONS)].copy()

    # Add team and clean name
    df = df.merge(player_teams, on=["player_id", "season"], how="left")
    df = df.merge(clean_names, on="player_id", how="left")
    # Replace the bugged display name (concatenated per game) with clean roster name
    df["player_display_name"] = df["player_name"].fillna(df["player_display_name"])
    df = df.drop(columns=["player_name"], errors="ignore")

    # --- 3. Compute per-game rates ---
    games = df["games"].clip(lower=1)

    df["pass_att_per_game"] = df["attempts"].fillna(0) / games
    df["rush_att_per_game"] = df["carries"].fillna(0) / games
    df["targets_per_game"] = df["targets"].fillna(0) / games
    df["receptions_per_game"] = df["receptions"].fillna(0) / games
    df["receiving_yards_per_game"] = df["receiving_yards"].fillna(0) / games
    df["rushing_yards_per_game"] = df["rushing_yards"].fillna(0) / games

    # --- 4. Efficiency metrics ---
    df["yards_per_carry"] = (
        df["rushing_yards"].fillna(0) / df["carries"].fillna(0).clip(lower=1)
    )
    df["yards_per_target"] = (
        df["receiving_yards"].fillna(0) / df["targets"].fillna(0).clip(lower=1)
    )
    df["catch_rate"] = (
        df["receptions"].fillna(0) / df["targets"].fillna(0).clip(lower=1)
    )
    df["yards_per_reception"] = (
        df["receiving_yards"].fillna(0) / df["receptions"].fillna(0).clip(lower=1)
    )
    df["racr_clean"] = df["racr"].fillna(0)
    df["air_yards_per_target"] = (
        df["receiving_air_yards"].fillna(0) / df["targets"].fillna(0).clip(lower=1)
    )

    # --- 5. Opportunity shares ---
    df["target_share_clean"] = df["target_share"].fillna(0)
    df["air_yards_share_clean"] = df["air_yards_share"].fillna(0)
    df["wopr"] = df["wopr"].fillna(0) if "wopr" in df.columns else 0

    # --- 6. TD indicators ---
    total_tds = (
        df["passing_tds"].fillna(0)
        + df["rushing_tds"].fillna(0)
        + df["receiving_tds"].fillna(0)
    )
    df["total_tds"] = total_tds
    df["tds_per_game"] = total_tds / games

    # --- 7. Fantasy points ---
    df["fantasy_points_ppr_calc"] = calculate_fantasy_points(df)
    df["ppg"] = df["fantasy_points_ppr_calc"] / games

    # --- 8. Age and experience ---
    age_df = _compute_age(rosters)
    df = df.merge(age_df, on=["player_id", "season"], how="left")

    age_peaks = {"QB": 29, "RB": 24.5, "WR": 26.5, "TE": 27}
    df["years_from_peak"] = df.apply(
        lambda r: r["age"] - age_peaks.get(r["position"], 27) if pd.notna(r["age"]) else 0,
        axis=1,
    )

    # --- 9. Weekly consistency ---
    consistency = _compute_weekly_consistency(weekly)
    df = df.merge(consistency, on=["player_id", "season"], how="left")

    # --- 10. EPA metrics ---
    df["passing_epa_clean"] = df["passing_epa"].fillna(0)
    df["rushing_epa_clean"] = df["rushing_epa"].fillna(0)
    df["receiving_epa_clean"] = df["receiving_epa"].fillna(0)

    # === NEW FEATURES ===

    # --- 11. Snap share (feature #4) ---
    print("  Computing snap share...")
    snap_pct = _compute_snap_pct(snap_counts, rosters)
    df = df.merge(snap_pct, on=["player_id", "season"], how="left")
    df["avg_snap_pct"] = df["avg_snap_pct"].fillna(0)

    # --- 12. Team change flag (feature #3) ---
    print("  Computing team changes...")
    team_changes = _compute_team_change(rosters)
    df = df.merge(team_changes, on=["player_id", "season"], how="left")
    df["changed_team"] = df["changed_team"].fillna(0).astype(int)

    # --- 13. Vegas implied team total (feature #5) ---
    print("  Computing Vegas implied totals...")
    vegas = _compute_vegas_implied_totals(schedules)
    df = df.merge(vegas, on=["team", "season"], how="left")
    df["team_implied_pts"] = df["team_implied_pts"].fillna(df["team_implied_pts"].median())

    # --- 14. QB quality for pass catchers (feature #6) ---
    print("  Computing QB quality metrics...")
    qb_quality = _compute_qb_quality(seasonal, rosters)
    df = df.merge(qb_quality, on=["team", "season"], how="left")
    df["qb_passing_epa"] = df["qb_passing_epa"].fillna(0)
    df["qb_comp_pct"] = df["qb_comp_pct"].fillna(df["qb_comp_pct"].median())
    df["qb_yards_per_att"] = df["qb_yards_per_att"].fillna(df["qb_yards_per_att"].median())

    # --- 15. Red zone stats (features #1 and #2) ---
    print("  Computing red zone stats...")
    rz_rush, rz_recv, rz_rush_team, rz_recv_team = _compute_redzone_stats(pbp_redzone)

    # Merge red zone rushing
    df = df.merge(rz_rush, on=["player_id", "season"], how="left")
    df = df.merge(rz_rush_team, on=["team", "season"], how="left")
    df["rz_carries"] = df["rz_carries"].fillna(0)
    df["rz_rush_tds"] = df["rz_rush_tds"].fillna(0)
    df["rz_rush_share"] = df["rz_carries"] / df["team_rz_carries"].clip(lower=1)

    # Merge red zone receiving
    df = df.merge(rz_recv, on=["player_id", "season"], how="left")
    df = df.merge(rz_recv_team, on=["team", "season"], how="left")
    df["rz_targets"] = df["rz_targets"].fillna(0)
    df["rz_rec_tds"] = df["rz_rec_tds"].fillna(0)
    df["rz_target_share"] = df["rz_targets"] / df["team_rz_targets"].clip(lower=1)

    # Combined red zone opps and expected TDs
    df["rz_opportunities"] = df["rz_carries"] + df["rz_targets"]

    # Historical red zone TD conversion rates (league average)
    # ~3.5% per rush, ~7% per target in the red zone
    df["expected_rz_tds"] = (df["rz_carries"] * 0.035) + (df["rz_targets"] * 0.07)
    df["actual_rz_tds"] = df["rz_rush_tds"] + df["rz_rec_tds"]
    df["td_over_expected"] = df["actual_rz_tds"] - df["expected_rz_tds"]

    # --- 16. Draft capital ---
    print("  Computing draft capital...")
    draft = _compute_draft_capital(draft_picks)
    df = df.merge(draft, on=["player_id"], how="left")
    # Years since draft — capital decays over time
    df["years_since_draft"] = df["season"] - df["draft_season"].fillna(df["season"])
    # Zero out capital for players 5+ years in (no longer relevant)
    df.loc[df["years_since_draft"] > 4, "draft_capital"] = 0
    df["draft_capital"] = df["draft_capital"].fillna(0)

    # --- 17. Select final feature columns ---
    feature_cols = [
        # Identifiers
        "player_id", "player_display_name", "season", "position", "team", "games",
        # Volume (per game)
        "pass_att_per_game", "rush_att_per_game", "targets_per_game",
        "receptions_per_game", "receiving_yards_per_game", "rushing_yards_per_game",
        # Opportunity shares
        "target_share_clean", "air_yards_share_clean", "wopr",
        # Efficiency
        "yards_per_carry", "yards_per_target", "catch_rate",
        "yards_per_reception", "racr_clean", "air_yards_per_target",
        # TDs
        "total_tds", "tds_per_game",
        # Red zone (NEW)
        "rz_carries", "rz_targets", "rz_opportunities",
        "rz_rush_share", "rz_target_share",
        "expected_rz_tds", "actual_rz_tds", "td_over_expected",
        # EPA
        "passing_epa_clean", "rushing_epa_clean", "receiving_epa_clean",
        # Career
        "age", "years_exp", "years_from_peak",
        # Snap share (NEW)
        "avg_snap_pct",
        # Team change (NEW)
        "changed_team",
        # Vegas implied total (NEW)
        "team_implied_pts",
        # QB quality (NEW)
        "qb_passing_epa", "qb_comp_pct", "qb_yards_per_att",
        # Draft capital (NEW)
        "draft_capital",
        # Consistency
        "weekly_pts_std", "weekly_pts_median", "weekly_cv", "weeks_played",
        # Target variable (current season points)
        "fantasy_points_ppr_calc", "ppg",
    ]

    result = df[feature_cols].copy()

    # Filter to players with meaningful sample: at least 4 games
    result = result[result["games"] >= 4].reset_index(drop=True)

    print(f"Feature matrix: {result.shape[0]} player-seasons, {result.shape[1]} columns")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    result.to_parquet(cache_path, index=False)
    print(f"Cached to {cache_path}")

    return result


if __name__ == "__main__":
    df = build_feature_matrix(force=True)
    print("\nShape:", df.shape)
    print("\nPositions:\n", df["position"].value_counts())
    print("\nNew feature coverage:")
    for col in ["avg_snap_pct", "changed_team", "team_implied_pts",
                 "qb_passing_epa", "rz_opportunities", "td_over_expected", "draft_capital"]:
        nonzero = (df[col] != 0).sum()
        print(f"  {col}: {nonzero} non-zero ({nonzero/len(df)*100:.0f}%)")
