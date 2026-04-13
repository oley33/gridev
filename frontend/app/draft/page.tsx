"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getDraftRecommendations, getProjections } from "../lib/api";
import type {
  DraftRecommendation,
  DraftSettings,
  PlayerProjection,
} from "../lib/types";
import PositionBadge from "../components/position-badge";
import PlayerModal from "../components/player-modal";

const DEFAULT_SETTINGS: DraftSettings = {
  league_size: 12,
  qb_slots: 1,
  rb_slots: 2,
  wr_slots: 2,
  te_slots: 1,
  flex_slots: 1,
};

const POSITIONS = ["QB", "RB", "WR", "TE"] as const;

export default function DraftPage() {
  const [settings] = useState<DraftSettings>(DEFAULT_SETTINGS);
  const [allPlayers, setAllPlayers] = useState<PlayerProjection[]>([]);
  const [draftedIds, setDraftedIds] = useState<Set<string>>(new Set());
  const [myRoster, setMyRoster] = useState<Record<string, string[]>>({
    QB: [],
    RB: [],
    WR: [],
    TE: [],
  });
  const [recommendations, setRecommendations] = useState<
    DraftRecommendation[]
  >([]);
  const [rosterNeeds, setRosterNeeds] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [recsLoading, setRecsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filterPos, setFilterPos] = useState<string>("ALL");
  const [selectedPlayer, setSelectedPlayer] =
    useState<PlayerProjection | null>(null);

  // Load all players once
  useEffect(() => {
    getProjections()
      .then((res) => {
        setAllPlayers(res.projections);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // Fetch recommendations whenever draft state changes
  const fetchRecs = useCallback(() => {
    setRecsLoading(true);
    getDraftRecommendations({
      settings,
      drafted_player_ids: Array.from(draftedIds),
      my_roster: myRoster,
    })
      .then((res) => {
        setRecommendations(res.best_available);
        setRosterNeeds(res.roster_needs);
      })
      .catch(() => {})
      .finally(() => setRecsLoading(false));
  }, [settings, draftedIds, myRoster]);

  useEffect(() => {
    if (!loading) fetchRecs();
  }, [fetchRecs, loading]);

  const markDrafted = (playerId: string, position: string, byMe: boolean) => {
    setDraftedIds((prev) => new Set(prev).add(playerId));
    if (byMe) {
      setMyRoster((prev) => ({
        ...prev,
        [position]: [...(prev[position] || []), playerId],
      }));
    }
  };

  const undoDraft = (playerId: string) => {
    setDraftedIds((prev) => {
      const next = new Set(prev);
      next.delete(playerId);
      return next;
    });
    setMyRoster((prev) => {
      const next: Record<string, string[]> = {};
      for (const [pos, ids] of Object.entries(prev)) {
        next[pos] = ids.filter((id) => id !== playerId);
      }
      return next;
    });
  };

  const resetDraft = () => {
    setDraftedIds(new Set());
    setMyRoster({ QB: [], RB: [], WR: [], TE: [] });
  };

  // Player board (available players, sorted by projected points)
  const availablePlayers = useMemo(() => {
    let players = allPlayers
      .filter((p) => !draftedIds.has(p.player_id))
      .sort((a, b) => b.proj_median - a.proj_median);

    if (filterPos !== "ALL") {
      players = players.filter((p) => p.position === filterPos);
    }
    if (search) {
      const q = search.toLowerCase();
      players = players.filter(
        (p) =>
          p.player_name.toLowerCase().includes(q) ||
          p.team.toLowerCase().includes(q)
      );
    }
    return players;
  }, [allPlayers, draftedIds, filterPos, search]);

  // My roster grouped
  const myRosterPlayers = useMemo(() => {
    const lookup = new Map(allPlayers.map((p) => [p.player_id, p]));
    const result: Record<string, PlayerProjection[]> = {};
    for (const [pos, ids] of Object.entries(myRoster)) {
      result[pos] = ids.map((id) => lookup.get(id)).filter(Boolean) as PlayerProjection[];
    }
    return result;
  }, [allPlayers, myRoster]);

  const totalMyPicks = Object.values(myRoster).flat().length;

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-6">
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-danger">
          Failed to connect to API. Is the backend running on localhost:8000?
          <div className="mt-1 text-sm opacity-75">{error}</div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Draft Assistant</h1>
          <p className="mt-1 text-sm text-muted">
            Track your draft live. Mark picks as they happen, get real-time recommendations.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted">
            {draftedIds.size} drafted &middot; {totalMyPicks} my picks
          </span>
          {draftedIds.size > 0 && (
            <button
              onClick={resetDraft}
              className="rounded-md border border-danger/30 px-3 py-1.5 text-sm text-danger hover:bg-danger/10 transition-colors"
            >
              Reset Draft
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: Recommendations */}
        <div className="lg:col-span-1 space-y-4">
          {/* My Roster */}
          <div className="rounded-lg border border-card-border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
              My Roster
            </h2>
            {POSITIONS.map((pos) => (
              <div key={pos} className="mb-2">
                <div className="flex items-center gap-2 mb-1">
                  <PositionBadge position={pos} />
                  <span className="text-xs text-muted">
                    {myRosterPlayers[pos]?.length || 0} / {settings[`${pos.toLowerCase()}_slots` as keyof DraftSettings]}
                    {rosterNeeds[pos] > 0 && (
                      <span className="ml-1 text-te">
                        (need {rosterNeeds[pos]})
                      </span>
                    )}
                  </span>
                </div>
                {myRosterPlayers[pos]?.map((p) => (
                  <div
                    key={p.player_id}
                    className="flex items-center justify-between rounded px-2 py-1 text-sm hover:bg-card-border/30"
                  >
                    <span>
                      {p.player_name}{" "}
                      <span className="text-muted text-xs">{p.team}</span>
                    </span>
                    <button
                      onClick={() => undoDraft(p.player_id)}
                      className="text-xs text-muted hover:text-danger"
                    >
                      undo
                    </button>
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* Recommendations */}
          <div className="rounded-lg border border-accent/30 bg-card p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
                Best Available
              </h2>
              {recsLoading && (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
              )}
            </div>
            <div className="space-y-1">
              {recommendations.slice(0, 15).map((rec, i) => (
                <div
                  key={rec.player_id}
                  className={`flex items-center justify-between rounded px-2 py-1.5 text-sm transition-colors hover:bg-card-border/30 ${
                    rec.positional_need ? "border-l-2 border-l-success" : ""
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs text-muted font-mono w-5">
                      {i + 1}
                    </span>
                    <PositionBadge position={rec.position} />
                    <span className="truncate font-medium">
                      {rec.player_name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 ml-2">
                    <span className="text-xs font-mono text-accent">
                      {rec.vor.toFixed(1)}
                    </span>
                    <button
                      onClick={() =>
                        markDrafted(rec.player_id, rec.position, true)
                      }
                      className="rounded bg-success/20 px-2 py-0.5 text-xs font-medium text-success hover:bg-success/30"
                    >
                      Mine
                    </button>
                    <button
                      onClick={() =>
                        markDrafted(rec.player_id, rec.position, false)
                      }
                      className="rounded bg-card-border px-2 py-0.5 text-xs font-medium text-muted hover:bg-card-border/80"
                    >
                      Taken
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Player board */}
        <div className="lg:col-span-2">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <div className="flex rounded-lg border border-card-border overflow-hidden">
              {["ALL", ...POSITIONS].map((pos) => (
                <button
                  key={pos}
                  onClick={() => setFilterPos(pos)}
                  className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                    filterPos === pos
                      ? "bg-accent text-white"
                      : "bg-card text-muted hover:text-foreground"
                  }`}
                >
                  {pos}
                </button>
              ))}
            </div>
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded-lg border border-card-border bg-card px-3 py-1.5 text-sm text-foreground placeholder-muted outline-none focus:border-accent focus:ring-1 focus:ring-accent w-full sm:w-48"
            />
            <span className="sm:ml-auto text-xs text-muted">
              {availablePlayers.length} available
            </span>
          </div>

          <div className="overflow-x-auto rounded-lg border border-card-border max-h-[70vh] overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="bg-card sticky top-0 z-10">
                <tr className="border-b border-card-border">
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
                    Player
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
                    Pos
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted hidden md:table-cell">
                    Team
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                    Proj
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted hidden sm:table-cell">
                    Boom%
                  </th>
                  <th className="px-3 py-2 text-center text-xs font-medium uppercase tracking-wider text-muted">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {availablePlayers.slice(0, 200).map((p, i) => (
                  <tr
                    key={p.player_id}
                    className={`border-b border-card-border/50 transition-colors hover:bg-card/80 ${
                      i % 2 === 0 ? "bg-background" : "bg-card/30"
                    }`}
                  >
                    <td
                      className="px-3 py-2 font-medium cursor-pointer hover:text-accent"
                      onClick={() => setSelectedPlayer(p)}
                    >
                      {p.player_name}
                    </td>
                    <td className="px-3 py-2">
                      <PositionBadge position={p.position} />
                    </td>
                    <td className="px-3 py-2 text-muted hidden md:table-cell">{p.team}</td>
                    <td className="px-3 py-2 text-right font-mono font-semibold">
                      {p.proj_median.toFixed(1)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono hidden sm:table-cell">
                      {(p.boom_pct * 100).toFixed(0)}%
                    </td>
                    <td className="px-3 py-2 text-center">
                      <div className="flex justify-center gap-1">
                        <button
                          onClick={() =>
                            markDrafted(p.player_id, p.position, true)
                          }
                          className="rounded bg-success/20 px-2 py-0.5 text-xs font-medium text-success hover:bg-success/30"
                        >
                          Mine
                        </button>
                        <button
                          onClick={() =>
                            markDrafted(p.player_id, p.position, false)
                          }
                          className="rounded bg-card-border px-2 py-0.5 text-xs font-medium text-muted hover:bg-card-border/80"
                        >
                          Taken
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <PlayerModal
        player={selectedPlayer}
        onClose={() => setSelectedPlayer(null)}
      />
    </div>
  );
}
