"""Compare our 2026 projections against current FantasyPros ECR.

nflreadpy only exposes the *current* season's FP ECR — no historical
snapshots — so we can't do a 5-year consensus backtest. Instead we compare
our top-N rankings today against the public consensus today and report
rank agreement, disagreement, and the players we're highest/lowest on.

Output: export/consensus_snapshot.json, consumed by the /performance page.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import nflreadpy as nfl
import pandas as pd
from scipy.stats import spearmanr

EXPORT_DIR = Path(__file__).resolve().parents[2] / "export"
TOP_N = 200


def _normalize_name(name: str) -> str:
    """Lowercase, strip suffixes (Jr, III, etc) and punctuation for matching."""
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)\b", "", s)
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def build_snapshot() -> dict:
    """Join our projections with current FP ECR and compute comparison stats."""
    proj_path = EXPORT_DIR / "projections_2026.json"
    with open(proj_path) as f:
        projections = json.load(f)

    proj_df = pd.DataFrame(projections)
    proj_df = proj_df[proj_df["position"].isin(["QB", "RB", "WR", "TE"])].copy()
    proj_df["match_key"] = proj_df["player_name"].map(_normalize_name) + "|" + proj_df["position"]

    # Our overall rank by projected points
    proj_df = proj_df.sort_values("proj_median", ascending=False).reset_index(drop=True)
    proj_df["our_rank"] = proj_df.index + 1
    proj_df["our_pos_rank"] = proj_df.groupby("position")["proj_median"].rank(
        method="min", ascending=False
    ).astype(int)

    # Load current consensus
    print("Loading FantasyPros ECR...")
    fp = nfl.load_ff_rankings().to_pandas()
    fp = fp[(fp["page_type"] == "redraft-overall") & (fp["pos"].isin(["QB", "RB", "WR", "TE"]))]
    fp = fp[["player", "pos", "team", "ecr", "scrape_date"]].copy()
    fp = fp.sort_values("ecr").reset_index(drop=True)
    fp["fp_rank"] = fp.index + 1
    fp["fp_pos_rank"] = fp.groupby("pos")["ecr"].rank(method="min").astype(int)
    fp["match_key"] = fp["player"].map(_normalize_name) + "|" + fp["pos"]

    scrape_date = str(fp["scrape_date"].iloc[0]) if len(fp) else None

    # Join on match_key
    merged = proj_df.merge(
        fp[["match_key", "fp_rank", "fp_pos_rank", "ecr"]],
        on="match_key",
        how="inner",
    )
    merged["rank_diff"] = merged["fp_rank"] - merged["our_rank"]  # positive = we rank higher
    merged = merged.sort_values("our_rank")

    # --- Metrics ---
    overall_rho = float(spearmanr(merged["our_rank"], merged["fp_rank"]).statistic)
    top_100 = merged[merged["our_rank"] <= 100]
    top_100_rho = float(spearmanr(top_100["our_rank"], top_100["fp_rank"]).statistic) if len(top_100) > 2 else 0.0

    per_position_agreement = {}
    for pos in ["QB", "RB", "WR", "TE"]:
        sub = merged[merged["position"] == pos]
        if len(sub) < 3:
            continue
        per_position_agreement[pos] = {
            "n_matched": int(len(sub)),
            "spearman": round(float(spearmanr(sub["our_pos_rank"], sub["fp_pos_rank"]).statistic), 3),
            "mean_abs_rank_diff": round(float((sub["our_pos_rank"] - sub["fp_pos_rank"]).abs().mean()), 2),
        }

    # Biggest disagreements: players where we rank MUCH higher or lower than FP.
    # Restrict to startable-tier players (our_rank <= TOP_N) so we don't surface
    # fringe bench players with noise-level rank differences.
    scope = merged[merged["our_rank"] <= TOP_N].copy()
    we_higher = scope.nlargest(15, "rank_diff")
    we_lower = scope.nsmallest(15, "rank_diff")

    def _row(r: pd.Series) -> dict:
        return {
            "player_id": r["player_id"],
            "player_name": r["player_name"],
            "position": r["position"],
            "team": r["team"],
            "proj_median": round(float(r["proj_median"]), 1),
            "our_rank": int(r["our_rank"]),
            "fp_rank": int(r["fp_rank"]),
            "rank_diff": int(r["rank_diff"]),
        }

    top_combined = [_row(r) for _, r in merged.nsmallest(50, "our_rank").iterrows()]

    # Who did FP include that we didn't project (and vice versa)?
    our_keys = set(proj_df[proj_df["our_rank"] <= TOP_N]["match_key"])
    fp_keys = set(fp[fp["fp_rank"] <= TOP_N]["match_key"])
    fp_only = fp[fp["match_key"].isin(fp_keys - our_keys)][["player", "pos", "team", "fp_rank"]].head(25)
    our_only = proj_df[proj_df["match_key"].isin(our_keys - fp_keys)][
        ["player_name", "position", "team", "our_rank"]
    ].head(25)

    result = {
        "scrape_date": scrape_date,
        "season": 2026,
        "n_matched": int(len(merged)),
        "n_our_top_n": int((proj_df["our_rank"] <= TOP_N).sum()),
        "n_fp_top_n": int(len(fp[fp["fp_rank"] <= TOP_N])),
        "top_n": TOP_N,
        "overall_spearman": round(overall_rho, 3),
        "top_100_spearman": round(top_100_rho, 3),
        "per_position": per_position_agreement,
        "top_players_combined": top_combined,
        "we_rank_higher": [_row(r) for _, r in we_higher.iterrows()],
        "we_rank_lower": [_row(r) for _, r in we_lower.iterrows()],
        "fp_only_top_n": fp_only.to_dict(orient="records"),
        "our_only_top_n": our_only.to_dict(orient="records"),
    }

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPORT_DIR / "consensus_snapshot.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Saved consensus snapshot to {out_path}")

    print(f"\nMatched {len(merged)} players against FP ECR ({scrape_date})")
    print(f"Overall Spearman rho: {overall_rho:.3f}")
    print(f"Top-100 Spearman rho: {top_100_rho:.3f}")
    print("\nPer-position agreement:")
    for pos, agg in per_position_agreement.items():
        print(f"  {pos}: rho={agg['spearman']:.3f}, "
              f"mean |rank diff|={agg['mean_abs_rank_diff']:.1f}, n={agg['n_matched']}")

    print("\nBiggest 'we rank higher' (we like more than FP does):")
    for r in result["we_rank_higher"][:10]:
        print(f"  {r['player_name']:<25} ({r['position']}) "
              f"our #{r['our_rank']:>3} vs FP #{r['fp_rank']:>3} "
              f"(diff={r['rank_diff']:+d})")

    print("\nBiggest 'we rank lower' (we like less than FP does):")
    for r in result["we_rank_lower"][:10]:
        print(f"  {r['player_name']:<25} ({r['position']}) "
              f"our #{r['our_rank']:>3} vs FP #{r['fp_rank']:>3} "
              f"(diff={r['rank_diff']:+d})")

    return result


if __name__ == "__main__":
    build_snapshot()
