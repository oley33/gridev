"""Projection data store — loads exported projections at startup.

Handles VOR calculation and filtering. All data is read-only after load.
"""

import json
from pathlib import Path

from src.api import config


class ProjectionStore:
    """In-memory store for player projections. Loaded once at startup."""

    def __init__(self) -> None:
        self._projections: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self._season: int = 0
        self._loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def season(self) -> int:
        return self._season

    def load(self, export_dir: str | None = None) -> None:
        """Load projections from the export directory."""
        export_path = Path(export_dir or config.EXPORT_DIR)

        # Find the most recent projections file
        proj_files = sorted(export_path.glob("projections_*.json"), reverse=True)
        if not proj_files:
            raise FileNotFoundError(
                f"No projection files found in {export_path}. "
                "Run `python -m src.models.export` first."
            )

        proj_file = proj_files[0]
        with open(proj_file) as f:
            self._projections = json.load(f)

        self._by_id = {p["player_id"]: p for p in self._projections}
        self._season = self._projections[0]["season"] if self._projections else 0
        self._loaded = True

        print(f"Loaded {len(self._projections)} projections for {self._season} season")

    def get_all(self, position: str | None = None) -> list[dict]:
        """Return all projections, optionally filtered by position."""
        if position:
            pos = position.upper()
            return [p for p in self._projections if p["position"] == pos]
        return list(self._projections)

    def get_player(self, player_id: str) -> dict | None:
        """Look up a single player by ID."""
        return self._by_id.get(player_id)

    def search(self, query: str) -> list[dict]:
        """Search players by name (case-insensitive substring match)."""
        q = query.lower()
        return [p for p in self._projections if q in p["player_name"].lower()]

    def compute_vor(
        self,
        league_size: int = 12,
        qb_slots: int = 1,
        rb_slots: int = 2,
        wr_slots: int = 2,
        te_slots: int = 1,
        flex_slots: int = 1,
        excluded_ids: set[str] | None = None,
    ) -> list[dict]:
        """Compute VOR for all players given league settings.

        VOR = player_proj - replacement_level_proj
        Replacement level = the Nth player at each position, where N is
        league_size * starters at that position.
        """
        excluded = excluded_ids or set()

        # Replacement level index per position
        replacement_rank = {
            "QB": league_size * qb_slots + 1,
            "RB": league_size * (rb_slots + flex_slots) + 1,  # FLEX inflates RB/WR replacement
            "WR": league_size * (wr_slots + flex_slots) + 1,
            "TE": league_size * te_slots + 1,
        }

        # Sort available players by projection at each position
        replacement_values = {}
        for pos in ["QB", "RB", "WR", "TE"]:
            pos_players = sorted(
                [p for p in self._projections if p["position"] == pos and p["player_id"] not in excluded],
                key=lambda p: p["proj_median"],
                reverse=True,
            )
            rank = replacement_rank[pos]
            if rank <= len(pos_players):
                replacement_values[pos] = pos_players[rank - 1]["proj_median"]
            else:
                replacement_values[pos] = 0

        # Compute VOR for each available player
        result = []
        for p in self._projections:
            if p["player_id"] in excluded:
                continue
            replacement = replacement_values.get(p["position"], 0)
            proj = dict(p)
            proj["vor"] = round(p["proj_median"] - replacement, 2)
            result.append(proj)

        result.sort(key=lambda p: p["vor"], reverse=True)
        return result


# Singleton instance
store = ProjectionStore()
