"use client";

import { Activity, ArrowLeft, BarChart3, CalendarDays } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { MATCH_STATUS } from "@/config/match-status";
import { PlayerHeatmap } from "@/features/matches/components/PlayerHeatmap";
import { PlayerIntensityChart } from "@/features/matches/components/PlayerIntensityChart";
import { PlayerKpiGrid } from "@/features/matches/components/PlayerKpiGrid";
import { PlayerPerformanceTimeline } from "@/features/matches/components/PlayerPerformanceTimeline";
import {
  formatMatchDate,
  formatTimestamp,
} from "@/lib/analytics-formatters";
import { ApiError, api } from "@/services/api-client";
import type { PlayerAnalyticsDetail } from "@/types/api";

interface PlayerMatchDetailProps {
  matchId: string;
  playerId: string;
}

export function PlayerMatchDetail({
  matchId,
  playerId,
}: PlayerMatchDetailProps) {
  const [detail, setDetail] = useState<PlayerAnalyticsDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [error, setError] = useState("Player performance could not be loaded.");

  useEffect(() => {
    const controller = new AbortController();
    api
      .getPlayerAnalytics(matchId, playerId, controller.signal)
      .then((response) => {
        setDetail(response.data);
        setError("");
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof ApiError && caught.status === 404
            ? "The match or player was not found."
            : "Check your connection and try again.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt, matchId, playerId]);

  if (loading) return <PlayerDetailSkeleton />;

  if (!detail) {
    return (
      <PageContainer className="max-w-6xl">
        <ErrorState
          message={error}
          onRetry={() => {
            setLoading(true);
            setAttempt((current) => current + 1);
          }}
          title="Player unavailable"
        />
      </PageContainer>
    );
  }

  const { match, player } = detail;
  const matchStatus = MATCH_STATUS[match.status];
  const hasAnyMetric = [
    player.rating,
    player.distance_m,
    player.avg_speed_kmh,
    player.max_speed_kmh,
    player.sprint_count,
    player.active_seconds,
    player.activity_count,
  ].some((value) => value !== null);

  return (
    <PageContainer className="max-w-6xl">
      <Link
        className="mb-4 inline-flex min-h-11 items-center gap-2 rounded-lg text-sm font-semibold text-slate-600 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2"
        href={`/matches/${matchId}?tab=players`}
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to players
      </Link>

      <Card padding="lg">
        <div className="flex min-w-0 flex-wrap items-center gap-4 sm:flex-nowrap">
          <Avatar className="size-16 text-lg" name={player.display_name} />
          <div className="min-w-0 flex-[1_1_12rem]">
            <div className="flex flex-wrap gap-2">
              <Badge variant="brand">{player.team.name}</Badge>
              <Badge variant={matchStatus.variant} dot>
                {matchStatus.label}
              </Badge>
              <Badge
                variant={
                  player.analytics_status === "available"
                    ? "success"
                    : player.analytics_status === "processing"
                      ? "info"
                      : player.analytics_status === "failed"
                        ? "danger"
                        : "neutral"
                }
              >
                Analytics {player.analytics_status}
              </Badge>
            </div>
            <h1 className="mt-3 break-words text-2xl font-bold tracking-tight text-slate-950 sm:text-3xl">
              {player.display_name}
            </h1>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-500">
              <span>{match.title ?? match.venue_name}</span>
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays className="size-4" aria-hidden="true" />
                {formatMatchDate(match.starts_at)}
              </span>
            </div>
          </div>
          <div className="ml-auto shrink-0 text-right">
            <p className="type-stat-label">LATEST JERSEY</p>
            <p className="type-stat-value mt-1 text-brand-800">
              {player.current_jersey !== null ? `#${player.current_jersey}` : "N/A"}
            </p>
          </div>
        </div>
      </Card>

      {player.analytics_status === "processing" ? (
        <Card className="mt-5">
          <EmptyState
            compact
            description="Metrics and movement visualizations will appear when processing finishes."
            icon={Activity}
            title="Player analytics are being processed"
          />
        </Card>
      ) : null}

      {player.analytics_status !== "processing" && !hasAnyMetric ? (
        <Card className="mt-5">
          <EmptyState
            compact
            description="No performance metrics have been calculated for this player. Missing data is shown as N/A."
            icon={BarChart3}
            title="Analytics unavailable"
          />
        </Card>
      ) : null}

      <div className="mt-6">
        <PlayerKpiGrid player={player} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="type-section-title text-slate-950">Position heatmap</h2>
          <p className="mb-4 mt-1 text-sm text-slate-500">
            Density from normalized player position samples.
          </p>
          <PlayerHeatmap
            processing={player.analytics_status === "processing"}
            samples={detail.position_samples}
          />
        </Card>
        <Card>
          <h2 className="type-section-title text-slate-950">
            Intensity by minute
          </h2>
          <p className="mb-4 mt-1 text-sm text-slate-500">
            Pipeline-provided activity intensity on a 0–100 scale.
          </p>
          <PlayerIntensityChart
            buckets={detail.intensity_buckets}
            processing={player.analytics_status === "processing"}
          />
        </Card>
      </div>

      <Card className="mt-5">
        <h2 className="type-section-title text-slate-950">
          Performance timeline
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Verified sprint, speed, intensity and jersey-change moments.
        </p>
        <PlayerPerformanceTimeline detail={detail} />
      </Card>

      <Card className="mt-5">
        <h2 className="type-section-title text-slate-950">Jersey history</h2>
        <p className="mt-1 text-sm text-slate-500">
          Jersey numbers belong to this match assignment, not the global player profile.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {player.jersey_history.map((item) => (
            <div
              className="flex items-center justify-between gap-4 rounded-xl bg-subtle p-4"
              key={item.assignment_id}
            >
              <span className="text-sm font-semibold tabular-nums text-slate-700">
                {formatElapsed(match.starts_at, item.started_at)}
                {" – "}
                {item.ended_at ? formatElapsed(match.starts_at, item.ended_at) : "Now"}
              </span>
              <span className="text-lg font-bold text-brand-800">
                #{item.jersey_number}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {player.max_speed_kmh !== null ? (
        <Card className="mt-5">
          <h2 className="type-section-title text-slate-950">Peak speed</h2>
          <p className="mt-3 text-2xl font-bold tabular-nums text-slate-950">
            {player.max_speed_kmh.toFixed(1)} km/h
          </p>
          {player.peak_speed_at_ms !== null ? (
            <p className="mt-1 text-sm font-semibold text-slate-500">
              At {formatTimestamp(player.peak_speed_at_ms)}
            </p>
          ) : null}
        </Card>
      ) : null}
    </PageContainer>
  );
}

function PlayerDetailSkeleton() {
  return (
    <PageContainer className="max-w-6xl">
      <Card>
        <div className="flex items-center gap-4">
          <div className="size-16 shrink-0 animate-pulse rounded-full bg-subtle" />
          <LoadingSkeleton lines={3} label="Loading player header" />
        </div>
      </Card>
      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 7 }, (_, index) => (
          <Card className="min-h-32 animate-pulse bg-subtle" key={index} />
        ))}
      </div>
      <Card className="mt-5">
        <LoadingSkeleton lines={4} label="Loading player analytics" />
      </Card>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="aspect-[100/64] animate-pulse rounded-xl bg-subtle" />
        </Card>
        <Card>
          <div className="h-52 animate-pulse rounded-xl bg-subtle" />
        </Card>
      </div>
    </PageContainer>
  );
}

function formatElapsed(matchStart: string, value: string): string {
  return formatTimestamp(
    Math.max(0, new Date(value).getTime() - new Date(matchStart).getTime()),
  );
}
