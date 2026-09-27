"use client";

import { ArrowLeft, Clock3 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ApiError, api } from "@/services/api-client";
import type { MatchDetail, MatchPlayer } from "@/types/api";

interface PlayerMatchDetailProps {
  matchId: string;
  playerId: string;
}

export function PlayerMatchDetail({
  matchId,
  playerId,
}: PlayerMatchDetailProps) {
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [player, setPlayer] = useState<MatchPlayer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("Player performance could not be loaded.");

  useEffect(() => {
    const controller = new AbortController();
    api
      .getPublicMatchDetail(matchId, controller.signal)
      .then((response) => {
        const found = response.data.players.find((item) => item.id === playerId);
        if (!found) {
          setError("This player is not assigned to the match.");
          return;
        }
        setDetail(response.data);
        setPlayer(found);
      })
      .catch((caught: unknown) => {
        setError(
          caught instanceof ApiError && caught.status === 404
            ? "The match or player was not found."
            : "Check your connection and try again.",
        );
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [matchId, playerId]);

  if (loading) {
    return (
      <PageContainer className="max-w-4xl">
        <Card>
          <LoadingSkeleton lines={7} label="Loading player match detail" />
        </Card>
      </PageContainer>
    );
  }

  if (!detail || !player) {
    return (
      <PageContainer className="max-w-4xl">
        <ErrorState message={error} title="Player unavailable" />
      </PageContainer>
    );
  }

  return (
    <PageContainer className="max-w-4xl">
      <Link
        className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-brand-800"
        href={`/matches/${matchId}?tab=players`}
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to players
      </Link>
      <Card padding="lg">
        <div className="flex min-w-0 items-center gap-4">
          <Avatar className="size-14 text-base" name={player.display_name} />
          <div className="min-w-0 flex-1">
            <Badge variant="brand">{player.team.name}</Badge>
            <h1 className="mt-2 truncate text-2xl font-bold tracking-tight text-slate-950">
              {player.display_name}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              {detail.match.title ?? detail.match.venue_name}
            </p>
          </div>
          <div className="text-right">
            <p className="type-stat-label">CURRENT JERSEY</p>
            <p className="type-stat-value mt-1 text-brand-800">
              {player.current_jersey !== null ? `#${player.current_jersey}` : "N/A"}
            </p>
          </div>
        </div>
      </Card>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="type-section-title text-slate-950">Jersey history</h2>
          <div className="mt-4 space-y-3">
            {player.jersey_history.map((item) => (
              <div
                className="flex items-center justify-between gap-4 rounded-xl bg-subtle p-4"
                key={item.assignment_id}
              >
                <span className="text-sm font-semibold text-slate-700">
                  {formatElapsed(detail.match.starts_at, item.started_at)}
                  {" – "}
                  {item.ended_at
                    ? formatElapsed(detail.match.starts_at, item.ended_at)
                    : "Now"}
                </span>
                <span className="text-lg font-bold text-brand-800">
                  #{item.jersey_number}
                </span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <h2 className="type-section-title text-slate-950">Performance</h2>
          <EmptyState
            compact
            description="Rating, distance, speed and sprint metrics have not been calculated."
            icon={Clock3}
            title="Analytics unavailable"
          />
        </Card>
      </div>
    </PageContainer>
  );
}

function formatElapsed(matchStart: string, value: string): string {
  const seconds = Math.max(
    0,
    Math.floor(
      (new Date(value).getTime() - new Date(matchStart).getTime()) / 1000,
    ),
  );
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(
    seconds % 60,
  ).padStart(2, "0")}`;
}
