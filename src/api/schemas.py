"""Pydantic models for request/response validation.

All API inputs and outputs are strictly typed. No raw dicts cross the API boundary.
"""

from pydantic import BaseModel, Field


class PlayerProjection(BaseModel):
    player_id: str
    player_name: str
    position: str
    team: str
    season: int
    age: float | None
    games_prev: int
    ppg_prev: float
    proj_median: float
    proj_mean: float
    floor_p10: float
    floor_p25: float
    ceiling_p75: float
    ceiling_p90: float
    proj_std: float
    boom_pct: float
    bust_pct: float
    vor: float | None = None


class ProjectionsResponse(BaseModel):
    season: int
    count: int
    projections: list[PlayerProjection]


class DraftSettings(BaseModel):
    league_size: int = Field(default=12, ge=4, le=32)
    qb_slots: int = Field(default=1, ge=1, le=3)
    rb_slots: int = Field(default=2, ge=1, le=4)
    wr_slots: int = Field(default=2, ge=1, le=4)
    te_slots: int = Field(default=1, ge=1, le=3)
    flex_slots: int = Field(default=1, ge=0, le=3)


class DraftRecommendRequest(BaseModel):
    settings: DraftSettings = Field(default_factory=DraftSettings)
    drafted_player_ids: list[str] = Field(
        default_factory=list,
        description="Player IDs already drafted by any team",
    )
    my_roster: dict[str, list[str]] = Field(
        default_factory=dict,
        description="My current roster: {position: [player_ids]}",
    )


class DraftRecommendation(BaseModel):
    player_id: str
    player_name: str
    position: str
    team: str
    vor: float
    proj_median: float
    floor_p10: float
    ceiling_p90: float
    boom_pct: float
    positional_need: bool


class DraftRecommendResponse(BaseModel):
    best_available: list[DraftRecommendation]
    roster_needs: dict[str, int]
