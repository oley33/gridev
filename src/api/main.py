"""Fantasy Football Projections API.

Serves pre-computed player projections with VOR ranking and draft
recommendations. All data is loaded at startup from exported model output.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api import config
from src.api.projections import store
from src.api.rate_limit import RateLimiter
from src.api.schemas import (
    DraftRecommendation,
    DraftRecommendRequest,
    DraftRecommendResponse,
    PlayerProjection,
    ProjectionsResponse,
)

rate_limiter = RateLimiter(config.RATE_LIMIT_PER_MINUTE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load projections once at startup."""
    store.load()
    yield


app = FastAPI(
    title="FF Projections API",
    description="Fantasy football player projections with uncertainty estimates",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    allow_credentials=False,
)


def _apply_rate_limit(request: Request) -> None:
    rate_limiter.check(request)


# --- Health ---


@app.get("/health")
def health():
    return {
        "status": "ok",
        "projections_loaded": store.is_loaded,
        "season": store.season,
    }


# --- Projections ---


@app.get(
    "/projections",
    response_model=ProjectionsResponse,
    dependencies=[Depends(_apply_rate_limit)],
)
def get_projections(
    position: str | None = Query(
        None, pattern="^(QB|RB|WR|TE)$", description="Filter by position"
    ),
):
    """Get all player projections, optionally filtered by position."""
    projections = store.get_all(position=position)
    return ProjectionsResponse(
        season=store.season,
        count=len(projections),
        projections=[PlayerProjection(**p) for p in projections],
    )


@app.get(
    "/players/{player_id}",
    response_model=PlayerProjection,
    dependencies=[Depends(_apply_rate_limit)],
)
def get_player(player_id: str):
    """Get a single player's projection by ID."""
    player = store.get_player(player_id)
    if player is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerProjection(**player)


@app.get(
    "/players",
    response_model=list[PlayerProjection],
    dependencies=[Depends(_apply_rate_limit)],
)
def search_players(
    q: str = Query(..., min_length=2, max_length=100, description="Search by player name"),
):
    """Search players by name."""
    results = store.search(q)
    return [PlayerProjection(**p) for p in results[:50]]


# --- VOR Rankings ---


@app.get(
    "/rankings",
    response_model=list[PlayerProjection],
    dependencies=[Depends(_apply_rate_limit)],
)
def get_rankings(
    league_size: int = Query(default=12, ge=4, le=32),
    qb_slots: int = Query(default=1, ge=1, le=3),
    rb_slots: int = Query(default=2, ge=1, le=4),
    wr_slots: int = Query(default=2, ge=1, le=4),
    te_slots: int = Query(default=1, ge=1, le=3),
    flex_slots: int = Query(default=1, ge=0, le=3),
    limit: int = Query(default=200, ge=1, le=500),
):
    """Get VOR-ranked players for given league settings."""
    ranked = store.compute_vor(
        league_size=league_size,
        qb_slots=qb_slots,
        rb_slots=rb_slots,
        wr_slots=wr_slots,
        te_slots=te_slots,
        flex_slots=flex_slots,
    )
    return [PlayerProjection(**p) for p in ranked[:limit]]


# --- Draft Recommendations ---


@app.post(
    "/draft/recommend",
    response_model=DraftRecommendResponse,
    dependencies=[Depends(_apply_rate_limit)],
)
def draft_recommend(req: DraftRecommendRequest):
    """Get draft recommendations based on current draft state.

    Send the list of already-drafted player IDs and your current roster.
    Returns the best available players ranked by VOR, with positional
    need flags based on your roster gaps.
    """
    settings = req.settings
    excluded = set(req.drafted_player_ids)

    # Compute VOR with drafted players excluded
    ranked = store.compute_vor(
        league_size=settings.league_size,
        qb_slots=settings.qb_slots,
        rb_slots=settings.rb_slots,
        wr_slots=settings.wr_slots,
        te_slots=settings.te_slots,
        flex_slots=settings.flex_slots,
        excluded_ids=excluded,
    )

    # Figure out what positions I still need
    slot_limits = {
        "QB": settings.qb_slots,
        "RB": settings.rb_slots,
        "WR": settings.wr_slots,
        "TE": settings.te_slots,
    }
    roster_counts = {pos: len(ids) for pos, ids in req.my_roster.items()}
    roster_needs = {
        pos: max(0, limit - roster_counts.get(pos, 0))
        for pos, limit in slot_limits.items()
    }

    # Build recommendations
    recommendations = []
    for p in ranked[:30]:
        recommendations.append(
            DraftRecommendation(
                player_id=p["player_id"],
                player_name=p["player_name"],
                position=p["position"],
                team=p["team"],
                vor=p["vor"],
                proj_median=p["proj_median"],
                floor_p10=p["floor_p10"],
                ceiling_p90=p["ceiling_p90"],
                boom_pct=p["boom_pct"],
                positional_need=roster_needs.get(p["position"], 0) > 0,
            )
        )

    return DraftRecommendResponse(
        best_available=recommendations,
        roster_needs=roster_needs,
    )


# --- Performance / Backtest ---


def _load_json(filename: str) -> dict:
    path = Path(config.EXPORT_DIR) / filename
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{filename} not found. Run the corresponding export script.",
        )
    with open(path) as f:
        return json.load(f)


@app.get("/performance/backtest", dependencies=[Depends(_apply_rate_limit)])
def get_backtest():
    """Walk-forward backtest results: our model vs naive vs weighted-history."""
    return _load_json("backtest.json")


@app.get("/performance/consensus", dependencies=[Depends(_apply_rate_limit)])
def get_consensus():
    """Current-year snapshot comparing our rankings vs FantasyPros ECR."""
    return _load_json("consensus_snapshot.json")
