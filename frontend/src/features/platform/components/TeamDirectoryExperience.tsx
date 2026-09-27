"use client";

import { CalendarDays, Shield, UsersRound } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";
import {
  DebouncedSearch,
  PlatformPagination,
} from "@/features/platform/components/DirectoryControls";
import { api } from "@/services/api-client";
import type { PageResponse, TeamDirectoryItem } from "@/types/api";

export function TeamDirectoryExperience() {
  const searchParams = useSearchParams();
  const requestKey = searchParams.toString();
  const page = positivePage(searchParams.get("page"));
  const [result, setResult] =
    useState<PageResponse<TeamDirectoryItem> | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function loadTeams() {
      await Promise.resolve();
      try {
        const response = await api.getTeams(
          {
            q: searchParams.get("q") ?? undefined,
            page,
            page_size: 20,
          },
          controller.signal,
        );
        setResult(response.data);
        setFailed(false);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void loadTeams();
    return () => controller.abort();
  }, [attempt, page, requestKey, searchParams]);

  return (
    <PageContainer className="max-w-6xl">
      <PageHeader
        description="Squads, participation and recent match context."
        eyebrow="Clubs & squads"
        title="Teams"
      />
      <Card className="mt-6 sm:mt-8" padding="sm">
        <DebouncedSearch label="Search teams" placeholder="Search team name" />
      </Card>

      {failed ? (
        <div className="mt-6">
          <ErrorState
            message="Teams could not be loaded."
            onRetry={() => setAttempt((current) => current + 1)}
            title="Team directory unavailable"
          />
        </div>
      ) : !result ? (
        <DirectorySkeleton />
      ) : result.items.length === 0 ? (
        <Card className="mt-6" padding="none">
          <EmptyState
            description="Teams appear when a match is created."
            icon={Shield}
            title={requestKey ? "No teams found" : "No teams yet"}
          />
        </Card>
      ) : (
        <>
          <p className="mt-6 text-sm font-semibold text-slate-500">
            {result.total} teams
          </p>
          <div className="mt-3 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {result.items.map((team) => (
              <Link
                className="rounded-2xl border border-border bg-white p-5 shadow-card transition hover:border-brand-200 focus-visible:outline-2 focus-visible:outline-brand-700"
                href={`/teams/${team.id}`}
                key={team.id}
              >
                <span className="flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                  <Shield className="size-5" aria-hidden="true" />
                </span>
                <h2 className="mt-4 truncate text-lg font-bold text-slate-950">
                  {team.name}
                </h2>
                <div className="mt-4 flex flex-wrap gap-4 text-sm text-slate-500">
                  <span className="inline-flex items-center gap-1.5">
                    <UsersRound className="size-4" aria-hidden="true" />
                    {team.player_count} players
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <CalendarDays className="size-4" aria-hidden="true" />
                    {team.match_count} matches
                  </span>
                </div>
              </Link>
            ))}
          </div>
          <PlatformPagination
            page={result.page}
            totalPages={result.total_pages}
          />
        </>
      )}
    </PageContainer>
  );
}

function DirectorySkeleton() {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <Card key={index}>
          <LoadingSkeleton lines={4} label="Loading team" />
        </Card>
      ))}
    </div>
  );
}

function positivePage(value: string | null) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}
