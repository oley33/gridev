"use client";

import { useEffect, useRef } from "react";
import type { ExplanationItem, PlayerProjection } from "../lib/types";
import PositionBadge from "./position-badge";

interface Props {
  player: PlayerProjection | null;
  onClose: () => void;
}

function StatBar({
  label,
  value,
  min,
  max,
  median,
  color,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  median: number;
  color: string;
}) {
  const range = max - min || 1;
  const pct = ((value - min) / range) * 100;
  const medianPct = ((median - min) / range) * 100;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-mono font-medium">{value.toFixed(1)}</span>
      </div>
      <div className="relative h-2 rounded-full bg-card-border/50">
        <div
          className={`absolute left-0 top-0 h-full rounded-full ${color}`}
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
        <div
          className="absolute top-[-2px] h-3 w-0.5 bg-foreground/60"
          style={{ left: `${Math.min(100, Math.max(0, medianPct))}%` }}
          title={`Median: ${median.toFixed(1)}`}
        />
      </div>
    </div>
  );
}

function ExplanationRow({
  item,
  kind,
  maxAbsImpact,
}: {
  item: ExplanationItem;
  kind: "pro" | "con";
  maxAbsImpact: number;
}) {
  const pct = Math.min(100, (Math.abs(item.impact) / maxAbsImpact) * 100);
  const color = kind === "pro" ? "bg-success/60" : "bg-danger/60";
  const sign = item.impact > 0 ? "+" : "";
  const impactColor = kind === "pro" ? "text-success" : "text-danger";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-medium text-foreground truncate">
          {item.label}
        </span>
        <span className={`font-mono shrink-0 ${impactColor}`}>
          {sign}
          {item.impact.toFixed(2)} PPG
        </span>
      </div>
      <div className="relative h-1.5 rounded-full bg-card-border/40">
        <div
          className={`absolute left-0 top-0 h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="text-[11px] text-muted font-mono">{item.value}</div>
    </div>
  );
}

export default function PlayerModal({ player, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (player) {
      dialog.showModal();
    } else {
      dialog.close();
    }
  }, [player]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  if (!player) return null;

  const projMax = Math.max(player.ceiling_p90, player.proj_median * 1.2);

  const allImpacts = [
    ...(player.explanation?.pros ?? []),
    ...(player.explanation?.cons ?? []),
  ].map((i) => Math.abs(i.impact));
  const maxAbsImpact = allImpacts.length > 0 ? Math.max(...allImpacts) : 1;

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 m-auto w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-card-border bg-card p-0 text-foreground backdrop:bg-black/60"
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
    >
      <div className="p-6">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold">{player.player_name}</h2>
              <PositionBadge position={player.position} />
            </div>
            <p className="mt-1 text-sm text-muted">
              {player.team} &middot; Age {player.age ?? "?"} &middot;{" "}
              {player.games_prev}G last season &middot; {player.ppg_prev.toFixed(1)} PPG
              {player.pos_rank != null && (
                <span className="ml-1 font-medium text-foreground">
                  &middot; Projected {player.position}{player.pos_rank}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-muted hover:bg-card-border/50 hover:text-foreground"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Projection range */}
        <div className="mb-6 space-y-3">
          <h3 className="text-sm font-semibold text-muted uppercase tracking-wider">
            Projection Range (Season Total)
          </h3>
          <StatBar
            label="Floor (P10)"
            value={player.floor_p10}
            min={0}
            max={projMax}
            median={player.proj_median}
            color="bg-danger/60"
          />
          <StatBar
            label="P25"
            value={player.floor_p25}
            min={0}
            max={projMax}
            median={player.proj_median}
            color="bg-te/60"
          />
          <StatBar
            label="Median"
            value={player.proj_median}
            min={0}
            max={projMax}
            median={player.proj_median}
            color="bg-accent/60"
          />
          <StatBar
            label="P75"
            value={player.ceiling_p75}
            min={0}
            max={projMax}
            median={player.proj_median}
            color="bg-rb/60"
          />
          <StatBar
            label="Ceiling (P90)"
            value={player.ceiling_p90}
            min={0}
            max={projMax}
            median={player.proj_median}
            color="bg-success/60"
          />
        </div>

        {/* Key stats grid */}
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-lg bg-background p-3 text-center">
            <div className="text-2xl font-bold font-mono">
              {player.proj_median.toFixed(1)}
            </div>
            <div className="text-xs text-muted">Projected Pts</div>
          </div>
          <div className="rounded-lg bg-background p-3 text-center">
            <div className="text-2xl font-bold font-mono text-success">
              {(player.boom_pct * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-muted">Boom Rate</div>
          </div>
          {player.relative_bust_pct != null ? (
            <div className="rounded-lg bg-background p-3 text-center">
              <div className="text-2xl font-bold font-mono text-danger">
                {(player.relative_bust_pct * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-muted">Bust Risk</div>
              {player.bust_threshold_rank != null && (
                <div className="text-[10px] text-muted mt-0.5 font-mono">
                  P(finish below {player.position}
                  {player.bust_threshold_rank})
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-lg bg-background p-3 text-center">
              <div className="text-2xl font-bold font-mono text-danger">
                {(player.bust_pct * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-muted">Bust Rate</div>
            </div>
          )}
          {player.vor !== null && player.vor !== undefined && (
            <div className="rounded-lg bg-background p-3 text-center">
              <div className="text-2xl font-bold font-mono text-accent">
                {player.vor.toFixed(1)}
              </div>
              <div className="text-xs text-muted">VOR</div>
            </div>
          )}
          <div className="rounded-lg bg-background p-3 text-center">
            <div className="text-2xl font-bold font-mono">
              {player.proj_std.toFixed(1)}
            </div>
            <div className="text-xs text-muted">Std Dev</div>
          </div>
          <div className="rounded-lg bg-background p-3 text-center">
            <div className="text-2xl font-bold font-mono">
              {(player.ceiling_p90 - player.floor_p10).toFixed(1)}
            </div>
            <div className="text-xs text-muted">Range</div>
          </div>
        </div>

        {/* Why is this player ranked here? — SHAP explanations */}
        {player.explanation &&
          (player.explanation.pros.length > 0 ||
            player.explanation.cons.length > 0) && (
            <div className="mt-6">
              <div className="mb-1 flex items-baseline justify-between">
                <h3 className="text-sm font-semibold text-muted uppercase tracking-wider">
                  Why this ranking?
                </h3>
                <span className="text-[10px] text-muted font-mono">
                  SHAP · impact in PPG
                </span>
              </div>
              <p className="mb-3 text-xs text-muted">
                Top features pushing this player&apos;s projection up or down,
                measured by their contribution to the XGBoost output.
              </p>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {player.explanation.pros.length > 0 && (
                  <div className="rounded-lg border border-success/25 bg-success/5 p-3">
                    <div className="mb-2 flex items-center gap-1.5">
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        className="text-success"
                      >
                        <polyline points="18 15 12 9 6 15" />
                      </svg>
                      <span className="text-xs font-semibold uppercase tracking-wider text-success">
                        Pros
                      </span>
                    </div>
                    <div className="space-y-2.5">
                      {player.explanation.pros.map((item) => (
                        <ExplanationRow
                          key={item.feature}
                          item={item}
                          kind="pro"
                          maxAbsImpact={maxAbsImpact}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {player.explanation.cons.length > 0 && (
                  <div className="rounded-lg border border-danger/25 bg-danger/5 p-3">
                    <div className="mb-2 flex items-center gap-1.5">
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        className="text-danger"
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                      <span className="text-xs font-semibold uppercase tracking-wider text-danger">
                        Cons
                      </span>
                    </div>
                    <div className="space-y-2.5">
                      {player.explanation.cons.map((item) => (
                        <ExplanationRow
                          key={item.feature}
                          item={item}
                          kind="con"
                          maxAbsImpact={maxAbsImpact}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
      </div>
    </dialog>
  );
}
