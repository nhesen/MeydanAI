"use client";

import { ArrowLeft, CalendarDays, Shield, UsersRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { PlatformMatchCard } from "@/features/platform/components/PlatformMatchCard";
import { PlayerDirectoryCard } from "@/features/platform/components/PlayerDirectoryExperience";
import { ApiError, api } from "@/services/api-client";
import type { TeamDetail } from "@/types/api";

export function TeamDetailExperience({ teamId }: { teamId: string }) {
  const [detail, setDetail] = useState<TeamDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      await Promise.resolve();
      try {
        const response = await api.getTeam(teamId, controller.signal);
        setDetail(response.data);
      } catch (caught: unknown) {
        if (!controller.signal.aborted) {
          setFailed(
            !(caught instanceof ApiError && caught.status === 404),
          );
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [teamId]);

  if (loading) {
    return (
      <PageContainer className="max-w-6xl">
        <Card>
          <LoadingSkeleton lines={6} label="Loading team" />
        </Card>
      </PageContainer>
    );
  }
  if (!detail) {
    return (
      <PageContainer className="max-w-6xl">
        <ErrorState
          message={
            failed ? "The team could not be loaded." : "This team does not exist."
          }
          title={failed ? "Team unavailable" : "Team not found"}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer className="max-w-6xl">
      <Link
        className="mb-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-slate-600 hover:text-brand-800"
        href="/teams"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to teams
      </Link>
      <Card padding="lg">
        <div className="flex flex-wrap items-center gap-4">
          <span className="flex size-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
            <Shield className="size-7" aria-hidden="true" />
          </span>
          <div className="min-w-0 flex-1">
            <Badge variant="brand">Team</Badge>
            <h1 className="mt-3 break-words text-2xl font-bold text-slate-950 sm:text-3xl">
              {detail.team.name}
            </h1>
          </div>
          <div className="flex gap-4 text-sm font-semibold text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <UsersRound className="size-4" aria-hidden="true" />
              {detail.team.player_count}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="size-4" aria-hidden="true" />
              {detail.team.match_count}
            </span>
          </div>
        </div>
      </Card>

      <section className="mt-8" aria-labelledby="team-players">
        <SectionHeader id="team-players" title="Players" />
        {detail.players.length ? (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {detail.players.map((player) => (
              <PlayerDirectoryCard key={player.id} player={player} />
            ))}
          </div>
        ) : (
          <Card className="mt-4" padding="none">
            <EmptyState
              compact
              description="No players have been assigned to this team."
              icon={UsersRound}
              title="No players"
            />
          </Card>
        )}
      </section>

      <section className="mt-8" aria-labelledby="team-matches">
        <SectionHeader id="team-matches" title="Recent matches" />
        {detail.recent_matches.length ? (
          <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {detail.recent_matches.map((item) => (
              <PlatformMatchCard item={item} key={item.match.id} />
            ))}
          </div>
        ) : (
          <Card className="mt-4" padding="none">
            <EmptyState
              compact
              description="No match history is available for this team."
              icon={CalendarDays}
              title="No matches"
            />
          </Card>
        )}
      </section>
    </PageContainer>
  );
}
