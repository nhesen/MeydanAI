"use client";

import { GitCompareArrows } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  formatCount,
  formatDistance,
  formatDuration,
  formatRating,
  formatSpeed,
} from "@/lib/analytics-formatters";
import { api } from "@/services/api-client";
import type { MatchPlayer, PlayerComparison as Comparison } from "@/types/api";

interface PlayerComparisonProps {
  matchId: string;
  players: MatchPlayer[];
}

export function PlayerComparison({
  matchId,
  players,
}: PlayerComparisonProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const playerIds = useMemo(
    () => new Set(players.map((player) => player.id)),
    [players],
  );
  const requestedLeft = searchParams.get("left") ?? "";
  const requestedRight = searchParams.get("right") ?? "";
  const leftId = playerIds.has(requestedLeft) ? requestedLeft : "";
  const rightId =
    playerIds.has(requestedRight) && requestedRight !== leftId
      ? requestedRight
      : "";
  const [attempt, setAttempt] = useState(0);
  const requestKey =
    leftId && rightId ? `${leftId}:${rightId}:${attempt}` : "";
  const [result, setResult] = useState<{
    key: string;
    data: Comparison | null;
    failed: boolean;
  }>({ key: "", data: null, failed: false });
  const comparison = result.key === requestKey ? result.data : null;
  const failed = result.key === requestKey && result.failed;
  const loading = Boolean(requestKey) && result.key !== requestKey;

  useEffect(() => {
    if (!leftId || !rightId) return;
    const controller = new AbortController();
    api
      .comparePlayers(matchId, leftId, rightId, controller.signal)
      .then((response) =>
        setResult({
          key: requestKey,
          data: response.data,
          failed: false,
        }),
      )
      .catch(() => {
        if (!controller.signal.aborted) {
          setResult({ key: requestKey, data: null, failed: true });
        }
      });
    return () => controller.abort();
  }, [leftId, matchId, requestKey, rightId]);

  function updateSelection(side: "left" | "right", playerId: string) {
    const next = new URLSearchParams(searchParams.toString());
    next.set("tab", "players");
    if (playerId) next.set(side, playerId);
    else next.delete(side);
    const otherSide = side === "left" ? "right" : "left";
    if (playerId && next.get(otherSide) === playerId) next.delete(otherSide);
    router.push(`/matches/${matchId}?${next.toString()}`);
  }

  return (
    <Card className="mb-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="type-section-title text-slate-950">Compare players</h2>
          <p className="mt-1 text-sm text-slate-500">
            Select two players registered in this match.
          </p>
        </div>
        <Badge variant="info">Match-specific</Badge>
      </div>

      {players.length < 2 ? (
        <EmptyState
          compact
          description="At least two assigned players are required for comparison."
          icon={GitCompareArrows}
          title="Comparison unavailable"
        />
      ) : (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <PlayerSelect
              label="First player"
              onChange={(value) => updateSelection("left", value)}
              players={players}
              unavailableId={rightId}
              value={leftId}
            />
            <PlayerSelect
              label="Second player"
              onChange={(value) => updateSelection("right", value)}
              players={players}
              unavailableId={leftId}
              value={rightId}
            />
          </div>

          {!leftId || !rightId ? (
            <EmptyState
              compact
              description="Choose two different players to compare their available metrics."
              icon={GitCompareArrows}
              title="Select players"
            />
          ) : loading ? (
            <div className="mt-6">
              <LoadingSkeleton lines={6} label="Loading player comparison" />
            </div>
          ) : failed ? (
            <ErrorState
              message="The selected players could not be compared. Check your connection and try again."
              onRetry={() => setAttempt((current) => current + 1)}
              title="Comparison unavailable"
            />
          ) : comparison ? (
            <ComparisonMetrics comparison={comparison} />
          ) : null}
        </>
      )}
    </Card>
  );
}

function PlayerSelect({
  label,
  onChange,
  players,
  unavailableId,
  value,
}: {
  label: string;
  onChange: (value: string) => void;
  players: MatchPlayer[];
  unavailableId: string;
  value: string;
}) {
  return (
    <label className="block min-w-0">
      <span className="mb-1.5 block text-sm font-semibold text-slate-700">
        {label}
      </span>
      <select
        className="min-h-11 w-full min-w-0 rounded-xl border border-border bg-white px-3 text-sm font-semibold text-slate-950 focus:border-brand-600 focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        <option value="">Choose player</option>
        {players.map((player) => (
          <option
            disabled={player.id === unavailableId}
            key={player.id}
            value={player.id}
          >
            {player.display_name} · {player.team.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function ComparisonMetrics({ comparison }: { comparison: Comparison }) {
  const metrics: Array<{
    label: string;
    format: (player: MatchPlayer) => string;
  }> = [
    { label: "Rating", format: (player) => formatRating(player.rating) },
    { label: "Distance", format: (player) => formatDistance(player.distance_m) },
    {
      label: "Average speed",
      format: (player) => formatSpeed(player.avg_speed_kmh),
    },
    {
      label: "Maximum speed",
      format: (player) => formatSpeed(player.max_speed_kmh),
    },
    {
      label: "Sprints",
      format: (player) => formatCount(player.sprint_count),
    },
    {
      label: "Active time",
      format: (player) => formatDuration(player.active_seconds),
    },
  ];

  return (
    <div className="mt-6">
      <div className="grid grid-cols-[minmax(0,1fr)_5rem_minmax(0,1fr)] items-center gap-2 sm:grid-cols-[minmax(0,1fr)_8rem_minmax(0,1fr)]">
        <PlayerIdentity player={comparison.left} />
        <span className="text-center text-xs font-bold uppercase tracking-wider text-slate-400">
          vs
        </span>
        <PlayerIdentity align="right" player={comparison.right} />
      </div>
      <div className="mt-4">
        {metrics.map((metric) => (
          <div
            className="grid grid-cols-[minmax(0,1fr)_5rem_minmax(0,1fr)] items-center gap-2 border-b border-border py-4 last:border-0 sm:grid-cols-[minmax(0,1fr)_8rem_minmax(0,1fr)]"
            key={metric.label}
          >
            <span className="min-w-0 break-words text-sm font-bold tabular-nums text-slate-950">
              {metric.format(comparison.left)}
            </span>
            <span className="text-center text-[0.7rem] font-semibold text-slate-500 sm:text-xs">
              {metric.label}
            </span>
            <span className="min-w-0 break-words text-right text-sm font-bold tabular-nums text-slate-950">
              {metric.format(comparison.right)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PlayerIdentity({
  align = "left",
  player,
}: {
  align?: "left" | "right";
  player: MatchPlayer;
}) {
  return (
    <div
      className={`flex min-w-0 items-center gap-2 ${
        align === "right" ? "flex-row-reverse text-right" : ""
      }`}
    >
      <Avatar className="size-9 shrink-0 text-xs" name={player.display_name} />
      <div className="min-w-0">
        <p className="truncate text-sm font-bold text-slate-950">
          {player.display_name}
        </p>
        <p className="truncate text-xs text-slate-500">{player.team.name}</p>
      </div>
    </div>
  );
}
