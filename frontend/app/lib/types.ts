export interface PlayerProjection {
  player_id: string;
  player_name: string;
  position: string;
  team: string;
  season: number;
  age: number | null;
  games_prev: number;
  ppg_prev: number;
  proj_median: number;
  proj_mean: number;
  floor_p10: number;
  floor_p25: number;
  ceiling_p75: number;
  ceiling_p90: number;
  proj_std: number;
  boom_pct: number;
  bust_pct: number;
  vor: number | null;
}

export interface ProjectionsResponse {
  season: number;
  count: number;
  projections: PlayerProjection[];
}

export interface DraftSettings {
  league_size: number;
  qb_slots: number;
  rb_slots: number;
  wr_slots: number;
  te_slots: number;
  flex_slots: number;
}

export interface DraftRecommendation {
  player_id: string;
  player_name: string;
  position: string;
  team: string;
  vor: number;
  proj_median: number;
  floor_p10: number;
  ceiling_p90: number;
  boom_pct: number;
  positional_need: boolean;
}

export interface DraftRecommendResponse {
  best_available: DraftRecommendation[];
  roster_needs: Record<string, number>;
}

export interface HealthResponse {
  status: string;
  projections_loaded: boolean;
  season: number;
}
