"use client";

import { BarChart3, UsersRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  DebouncedSearch,
  PlatformPagination,
  updateQueryHref,
} from "@/features/platform/components/DirectoryControls";
import {
  formatDistance,
  formatRating,
  formatSpeed,
} from "@/lib/analytics-formatters";
import { api } from "@/services/api-client";
import type {
  PageResponse,
  PlayerDirectoryItem,
  TeamDirectoryItem,
} from "@/types/api";

export function PlayerDirectoryExperience() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestKey = searchParams.toString();
  const page = positivePage(searchParams.get("page"));
  const [result, setResult] =
    useState<PageResponse<PlayerDirectoryItem> | null>(null);
  const [teams, setTeams] = useState<TeamDirectoryItem[]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function loadTeams() {
      await Promise.resolve();
      try {
        const response = await api.getTeams(
          { page_size: 50 },
          controller.signal,
        );
        setTeams(response.data.items);
      } catch {
        if (!controller.signal.aborted) setTeams([]);
      }
    }
    void loadTeams();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function loadPlayers() {
      await Promise.resolve();
      try {
        const response = await api.getPlayers(
          {
            q: searchParams.get("q") ?? undefined,
            team_id: searchParams.get("team") ?? undefined,
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
    void loadPlayers();
    return () => controller.abort();
  }, [attempt, page, requestKey, searchParams]);

  return (
    <PageContainer className="max-w-6xl">
      <PageHeader
        description="Global player identities with verified recent match context."
        eyebrow="Performance directory"
        title="Players"
      />
      <Card className="mt-6 sm:mt-8" padding="sm">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(10rem,16rem)]">
          <DebouncedSearch
            label="Search players"
            placeholder="Search player name"
          />
          <select
            aria-label="Filter by team"
            className={filterClass}
            onChange={(event) =>
              router.push(
                updateQueryHref(pathname, searchParams, {
                  team: event.target.value,
                }),
              )
            }
            value={searchParams.get("team") ?? ""}
          >
            <option value="">All teams</option>
            {teams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {failed ? (
        <div className="mt-6">
          <ErrorState
            message="Players could not be loaded."
            onRetry={() => setAttempt((current) => current + 1)}
            title="Player directory unavailable"
          />
        </div>
      ) : !result ? (
        <DirectorySkeleton />
      ) : result.items.length === 0 ? (
        <Card className="mt-6" padding="none">
          <EmptyState
            description="Players appear after joining or being assigned to a match."
            icon={UsersRound}
            title={requestKey ? "No players found" : "No players yet"}
          />
        </Card>
      ) : (
        <>
          <p className="mt-6 text-sm font-semibold text-slate-500">
            {result.total} players
          </p>
          <div className="mt-3 grid gap-4 lg:grid-cols-2">
            {result.items.map((player) => (
              <PlayerDirectoryCard key={player.id} player={player} />
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

export function PlayerDirectoryCard({
  player,
}: {
  player: PlayerDirectoryItem;
}) {
  const performance = player.recent_performance;
  return (
    <Link
      className="block rounded-2xl border border-border bg-white p-4 shadow-card transition hover:border-brand-200 focus-visible:outline-2 focus-visible:outline-brand-700"
      href={`/players/${player.id}`}
    >
      <div className="flex min-w-0 items-center gap-3">
        <Avatar className="size-12" name={player.display_name} />
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-bold text-slate-950">
            {player.display_name}
          </h2>
          <p className="mt-1 truncate text-sm text-slate-500">
            {performance?.team.name ?? "No recent team context"}
          </p>
        </div>
        {performance ? (
          <Badge variant={performance.rating === null ? "neutral" : "brand"}>
            {formatRating(performance.rating)}
          </Badge>
        ) : null}
      </div>
      {performance ? (
        <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-subtle p-3 text-center">
          <Metric label="Distance" value={formatDistance(performance.distance_m)} />
          <Metric label="Max speed" value={formatSpeed(performance.max_speed_kmh)} />
          <Metric
            label="Sprints"
            value={performance.sprint_count?.toString() ?? "N/A"}
          />
        </div>
      ) : (
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-subtle p-3 text-sm text-slate-500">
          <BarChart3 className="size-4" aria-hidden="true" />
          No match analytics available
        </div>
      )}
    </Link>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="truncate text-xs font-bold tabular-nums text-slate-950">
        {value}
      </p>
      <p className="mt-1 truncate text-[0.65rem] font-semibold text-slate-500">
        {label}
      </p>
    </div>
  );
}

function DirectorySkeleton() {
  return (
    <div className="mt-6 grid gap-4 lg:grid-cols-2">
      {Array.from({ length: 6 }, (_, index) => (
        <Card key={index}>
          <LoadingSkeleton lines={4} label="Loading player" />
        </Card>
      ))}
    </div>
  );
}

function positivePage(value: string | null) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

const filterClass =
  "h-11 min-w-0 rounded-xl border border-border bg-white px-3 text-sm text-slate-700 focus:border-brand-600 focus:outline-2 focus:outline-brand-600";
