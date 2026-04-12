import type {
  PlayerProjection,
  ProjectionsResponse,
  DraftRecommendResponse,
  DraftSettings,
  HealthResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch("/health");
}

export async function getProjections(
  position?: string
): Promise<ProjectionsResponse> {
  const params = position ? `?position=${position}` : "";
  return apiFetch(`/projections${params}`);
}

export async function getPlayer(
  playerId: string
): Promise<PlayerProjection> {
  return apiFetch(`/players/${encodeURIComponent(playerId)}`);
}

export async function searchPlayers(
  query: string
): Promise<PlayerProjection[]> {
  return apiFetch(`/players?q=${encodeURIComponent(query)}`);
}

export async function getRankings(params: {
  league_size?: number;
  qb_slots?: number;
  rb_slots?: number;
  wr_slots?: number;
  te_slots?: number;
  flex_slots?: number;
  limit?: number;
}): Promise<PlayerProjection[]> {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) searchParams.set(key, String(value));
  }
  return apiFetch(`/rankings?${searchParams}`);
}

export async function getDraftRecommendations(body: {
  settings?: DraftSettings;
  drafted_player_ids?: string[];
  my_roster?: Record<string, string[]>;
}): Promise<DraftRecommendResponse> {
  return apiFetch("/draft/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
