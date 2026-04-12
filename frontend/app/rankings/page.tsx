"use client";

import { useCallback, useEffect, useState } from "react";
import { getRankings } from "../lib/api";
import type { PlayerProjection } from "../lib/types";
import PositionBadge from "../components/position-badge";
import PlayerModal from "../components/player-modal";

interface LeagueSettings {
  league_size: number;
  qb_slots: number;
  rb_slots: number;
  wr_slots: number;
  te_slots: number;
  flex_slots: number;
}

const DEFAULT_SETTINGS: LeagueSettings = {
  league_size: 12,
  qb_slots: 1,
  rb_slots: 2,
  wr_slots: 2,
  te_slots: 1,
  flex_slots: 1,
};

function SettingInput({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-sm text-muted whitespace-nowrap">{label}</label>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-16 rounded border border-card-border bg-background px-2 py-1 text-center text-sm font-mono text-foreground outline-none focus:border-accent"
      />
    </div>
  );
}

export default function RankingsPage() {
  const [settings, setSettings] = useState<LeagueSettings>(DEFAULT_SETTINGS);
  const [rankings, setRankings] = useState<PlayerProjection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerProjection | null>(
    null
  );

  const fetchRankings = useCallback(() => {
    setLoading(true);
    setError(null);
    getRankings({ ...settings, limit: 300 })
      .then(setRankings)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [settings]);

  useEffect(() => {
    fetchRankings();
  }, [fetchRankings]);

  const updateSetting = (key: keyof LeagueSettings, val: number) => {
    setSettings((prev) => ({ ...prev, [key]: val }));
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">VOR Rankings</h1>
        <p className="mt-1 text-sm text-muted">
          Value Over Replacement rankings, customized to your league settings
        </p>
      </div>

      {/* Settings */}
      <div className="mb-6 rounded-lg border border-card-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">
          League Settings
        </h2>
        <div className="flex flex-wrap gap-4">
          <SettingInput
            label="Teams"
            value={settings.league_size}
            min={4}
            max={32}
            onChange={(v) => updateSetting("league_size", v)}
          />
          <SettingInput
            label="QB"
            value={settings.qb_slots}
            min={1}
            max={3}
            onChange={(v) => updateSetting("qb_slots", v)}
          />
          <SettingInput
            label="RB"
            value={settings.rb_slots}
            min={1}
            max={4}
            onChange={(v) => updateSetting("rb_slots", v)}
          />
          <SettingInput
            label="WR"
            value={settings.wr_slots}
            min={1}
            max={4}
            onChange={(v) => updateSetting("wr_slots", v)}
          />
          <SettingInput
            label="TE"
            value={settings.te_slots}
            min={1}
            max={3}
            onChange={(v) => updateSetting("te_slots", v)}
          />
          <SettingInput
            label="FLEX"
            value={settings.flex_slots}
            min={0}
            max={3}
            onChange={(v) => updateSetting("flex_slots", v)}
          />
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/30 bg-danger/10 p-4 text-danger">
          Failed to load rankings. Is the API running on localhost:8000?
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
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted w-12">
                  Rank
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
                  Player
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
                  Pos
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted">
                  Team
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-accent">
                  VOR
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                  Proj
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                  Floor
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                  Ceiling
                </th>
                <th className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted">
                  Boom%
                </th>
              </tr>
            </thead>
            <tbody>
              {rankings.map((p, i) => (
                <tr
                  key={p.player_id}
                  className={`border-b border-card-border/50 cursor-pointer transition-colors hover:bg-card/80 ${
                    i % 2 === 0 ? "bg-background" : "bg-card/30"
                  }`}
                  onClick={() => setSelectedPlayer(p)}
                >
                  <td className="px-3 py-2 font-mono text-muted">{i + 1}</td>
                  <td className="px-3 py-2 font-medium">{p.player_name}</td>
                  <td className="px-3 py-2">
                    <PositionBadge position={p.position} />
                  </td>
                  <td className="px-3 py-2 text-muted">{p.team}</td>
                  <td className="px-3 py-2 text-right font-mono font-bold text-accent">
                    {(p.vor ?? 0).toFixed(1)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">
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
