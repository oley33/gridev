"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getProjections } from "./lib/api";
import type { PlayerProjection } from "./lib/types";
import PositionBadge from "./components/position-badge";
import PlayerModal from "./components/player-modal";

type SortKey = keyof PlayerProjection;
type SortDir = "asc" | "desc";

const POSITIONS = ["ALL", "QB", "RB", "WR", "TE"] as const;

export default function ProjectionsPage() {
  const [projections, setProjections] = useState<PlayerProjection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState<string>("ALL");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("proj_median");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerProjection | null>(
    null
  );

  useEffect(() => {
    setLoading(true);
    setError(null);
    getProjections(position === "ALL" ? undefined : position)
      .then((res) => setProjections(res.projections))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [position]);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("desc");
      }
    },
    [sortKey]
  );

  const filtered = useMemo(() => {
    let data = projections;
    if (search) {
      const q = search.toLowerCase();
      data = data.filter(
        (p) =>
          p.player_name.toLowerCase().includes(q) ||
          p.team.toLowerCase().includes(q)
      );
    }
    data = [...data].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc"
          ? av.localeCompare(bv)
          : bv.localeCompare(av);
      }
      return sortDir === "asc"
        ? (av as number) - (bv as number)
        : (bv as number) - (av as number);
    });
    return data;
  }, [projections, search, sortKey, sortDir]);

  const SortHeader = ({
    label,
    field,
    className,
  }: {
    label: string;
    field: SortKey;
    className?: string;
  }) => (
    <th
      className={`cursor-pointer px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted hover:text-foreground select-none ${className || ""}`}
      onClick={() => handleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortKey === field && (
          <span className="text-accent">
            {sortDir === "asc" ? "\u25B2" : "\u25BC"}
          </span>
        )}
      </span>
    </th>
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Player Projections</h1>
        <p className="mt-1 text-sm text-muted">
          ML-powered 2025 fantasy football projections with uncertainty estimates
        </p>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg border border-card-border overflow-hidden">
          {POSITIONS.map((pos) => (
            <button
              key={pos}
              onClick={() => setPosition(pos)}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                position === pos
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
          placeholder="Search players or teams..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-lg border border-card-border bg-card px-3 py-1.5 text-sm text-foreground placeholder-muted outline-none focus:border-accent focus:ring-1 focus:ring-accent w-64"
        />
        <span className="ml-auto text-sm text-muted">
          {filtered.length} players
        </span>
      </div>

      {/* Table */}
      {error ? (
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-danger">
          Failed to load projections. Is the API running on localhost:8000?
          <div className="mt-1 text-sm opacity-75">{error}</div>
        </div>
      ) : loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-card-border">
          <table className="w-full text-sm">
            <thead className="bg-card">
              <tr className="border-b border-card-border">
                <SortHeader label="Player" field="player_name" className="text-left" />
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
                  Pos
                </th>
                <SortHeader label="Team" field="team" className="text-left" />
                <SortHeader label="Proj" field="proj_median" className="text-right" />
                <SortHeader label="Floor" field="floor_p10" className="text-right" />
                <SortHeader label="Ceiling" field="ceiling_p90" className="text-right" />
                <SortHeader label="Boom%" field="boom_pct" className="text-right" />
                <SortHeader label="Bust%" field="bust_pct" className="text-right" />
                <SortHeader label="Std" field="proj_std" className="text-right" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, i) => (
                <tr
                  key={p.player_id}
                  className={`border-b border-card-border/50 cursor-pointer transition-colors hover:bg-card/80 ${
                    i % 2 === 0 ? "bg-background" : "bg-card/30"
                  }`}
                  onClick={() => setSelectedPlayer(p)}
                >
                  <td className="px-3 py-2 font-medium">{p.player_name}</td>
                  <td className="px-3 py-2">
                    <PositionBadge position={p.position} />
                  </td>
                  <td className="px-3 py-2 text-muted">{p.team}</td>
                  <td className="px-3 py-2 text-right font-mono font-semibold">
                    {p.proj_median.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-danger/80">
                    {p.floor_p10.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-success/80">
                    {p.ceiling_p90.toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    {p.boom_pct.toFixed(0)}%
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
                    {p.bust_pct.toFixed(0)}%
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-muted">
                    {p.proj_std.toFixed(1)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <PlayerModal
        player={selectedPlayer}
        onClose={() => setSelectedPlayer(null)}
      />
    </div>
  );
}
