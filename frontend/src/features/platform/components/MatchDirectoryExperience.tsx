"use client";

import { CalendarDays, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
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
  updateQueryHref,
} from "@/features/platform/components/DirectoryControls";
import { PlatformMatchCard } from "@/features/platform/components/PlatformMatchCard";
import { api } from "@/services/api-client";
import type {
  MatchListItem,
  MatchSummary,
  PageResponse,
  TeamDirectoryItem,
} from "@/types/api";

export function MatchDirectoryExperience() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestKey = searchParams.toString();
  const [result, setResult] = useState<PageResponse<MatchListItem> | null>(null);
  const [teams, setTeams] = useState<TeamDirectoryItem[]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const page = positivePage(searchParams.get("page"));
  const status = (searchParams.get("status") ?? "") as
    | MatchSummary["status"]
    | "";

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
    async function loadMatches() {
      await Promise.resolve();
      try {
        const response = await api.getPlatformMatches(
          {
            q: searchParams.get("q") ?? undefined,
            status,
            team_id: searchParams.get("team") ?? undefined,
            date_from: searchParams.get("from") ?? undefined,
            date_to: searchParams.get("to") ?? undefined,
            page,
            page_size: 12,
          },
          controller.signal,
        );
        setResult(response.data);
        setFailed(false);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void loadMatches();
    return () => controller.abort();
  }, [attempt, page, requestKey, searchParams, status]);

  return (
    <PageContainer className="max-w-7xl">
      <PageHeader
        action={
          <Link
            className="inline-flex h-11 items-center justify-center rounded-xl bg-brand-700 px-4 text-sm font-semibold text-white hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-brand-700"
            href="/matches/new"
          >
            Create match
          </Link>
        }
        description="Search and filter scheduled, live, processing and completed matches."
        eyebrow="Match center"
        title="Matches"
      />

      <Card className="mt-6 sm:mt-8" padding="sm">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-500 sm:hidden">
          <SlidersHorizontal className="size-4" aria-hidden="true" />
          Filters
        </div>
        <div className="mt-3 grid gap-3 sm:mt-0 lg:grid-cols-[minmax(14rem,1fr)_repeat(4,minmax(9rem,auto))]">
          <DebouncedSearch
            label="Search matches"
            placeholder="Search title, venue or team"
          />
          <select
            aria-label="Match status"
            className={filterClass}
            onChange={(event) =>
              router.push(
                updateQueryHref(pathname, searchParams, {
                  status: event.target.value,
                }),
              )
            }
            value={status}
          >
            <option value="">All statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="live">Live</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            aria-label="Team"
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
          <input
            aria-label="From date"
            className={filterClass}
            onChange={(event) =>
              router.push(
                updateQueryHref(pathname, searchParams, {
                  from: event.target.value,
                }),
              )
            }
            type="date"
            value={searchParams.get("from") ?? ""}
          />
          <input
            aria-label="To date"
            className={filterClass}
            onChange={(event) =>
              router.push(
                updateQueryHref(pathname, searchParams, {
                  to: event.target.value,
                }),
              )
            }
            type="date"
            value={searchParams.get("to") ?? ""}
          />
        </div>
      </Card>

      {failed ? (
        <div className="mt-6">
          <ErrorState
            message="Matches could not be loaded. Check your filters or connection."
            onRetry={() => setAttempt((current) => current + 1)}
            title="Match directory unavailable"
          />
        </div>
      ) : !result ? (
        <DirectorySkeleton />
      ) : result.items.length === 0 ? (
        <Card className="mt-6" padding="none">
          <EmptyState
            action={
              <Link
                className="font-semibold text-brand-700 hover:text-brand-900"
                href="/matches/new"
              >
                Create match
              </Link>
            }
            description="Adjust the filters or create a new match."
            icon={CalendarDays}
            title={requestKey ? "No matches found" : "No matches yet"}
          />
        </Card>
      ) : (
        <>
          <p className="mt-6 text-sm font-semibold text-slate-500">
            {result.total} matches
          </p>
          <div className="mt-3 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {result.items.map((item) => (
              <PlatformMatchCard item={item} key={item.match.id} />
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
    <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <Card key={index}>
          <LoadingSkeleton lines={5} label="Loading match" />
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
  "h-11 min-w-0 rounded-xl border border-border bg-white px-3 text-sm text-slate-700 focus:border-brand-600 focus:outline-2 focus:outline-offset-1 focus:outline-brand-600";
