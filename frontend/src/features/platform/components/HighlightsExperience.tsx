"use client";

import { Clapperboard, RotateCcw } from "lucide-react";
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
  PlatformPagination,
  updateQueryHref,
} from "@/features/platform/components/DirectoryControls";
import {
  HIGHLIGHT_LABELS,
  PlatformHighlightCard,
} from "@/features/platform/components/PlatformHighlightCard";
import { api } from "@/services/api-client";
import type {
  HighlightType,
  MatchListItem,
  PageResponse,
  PlatformHighlight,
  PlayerDirectoryItem,
} from "@/types/api";

const HIGHLIGHT_TYPES = Object.entries(HIGHLIGHT_LABELS) as [
  HighlightType,
  string,
][];

export function HighlightsExperience() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestKey = searchParams.toString();
  const page = positivePage(searchParams.get("page"));
  const [result, setResult] =
    useState<PageResponse<PlatformHighlight> | null>(null);
  const [matches, setMatches] = useState<MatchListItem[]>([]);
  const [players, setPlayers] = useState<PlayerDirectoryItem[]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function loadOptions() {
      await Promise.resolve();
      const [matchResult, playerResult] = await Promise.allSettled([
        api.getPlatformMatches(
          { page: 1, page_size: 100 },
          controller.signal,
        ),
        api.getPlayers({ page: 1, page_size: 100 }, controller.signal),
      ]);
      if (controller.signal.aborted) return;
      setMatches(
        matchResult.status === "fulfilled"
          ? matchResult.value.data.items
          : [],
      );
      setPlayers(
        playerResult.status === "fulfilled"
          ? playerResult.value.data.items
          : [],
      );
    }
    void loadOptions();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function loadHighlights() {
      await Promise.resolve();
      try {
        const response = await api.getHighlights(
          {
            match_id: searchParams.get("match") ?? undefined,
            player_id: searchParams.get("player") ?? undefined,
            highlight_type:
              (searchParams.get("type") as HighlightType | null) ?? undefined,
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
    void loadHighlights();
    return () => controller.abort();
  }, [attempt, page, requestKey, searchParams]);

  function changeFilter(key: string, value: string) {
    router.push(updateQueryHref(pathname, searchParams, { [key]: value }));
  }

  return (
    <PageContainer className="max-w-7xl">
      <PageHeader
        description="Real manual and AI-detected match moments, collected in one library."
        eyebrow="Match moments"
        title="Highlights"
      />

      <Card className="mt-6 sm:mt-8" padding="sm">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_0.75fr_auto]">
          <select
            aria-label="Filter highlights by match"
            className={filterClass}
            onChange={(event) => changeFilter("match", event.target.value)}
            value={searchParams.get("match") ?? ""}
          >
            <option value="">All matches</option>
            {matches.map(({ match }) => (
              <option key={match.id} value={match.id}>
                {match.title ?? match.venue_name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter highlights by player"
            className={filterClass}
            onChange={(event) => changeFilter("player", event.target.value)}
            value={searchParams.get("player") ?? ""}
          >
            <option value="">All players</option>
            {players.map((player) => (
              <option key={player.id} value={player.id}>
                {player.display_name}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter highlights by type"
            className={filterClass}
            onChange={(event) => changeFilter("type", event.target.value)}
            value={searchParams.get("type") ?? ""}
          >
            <option value="">All types</option>
            {HIGHLIGHT_TYPES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <Link
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-border bg-white px-4 text-sm font-semibold text-slate-600 hover:border-brand-300 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-brand-700"
            href={pathname}
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            Reset
          </Link>
        </div>
      </Card>

      {failed ? (
        <div className="mt-6">
          <ErrorState
            message="Highlights could not be loaded."
            onRetry={() => setAttempt((current) => current + 1)}
            title="Highlight library unavailable"
          />
        </div>
      ) : !result ? (
        <HighlightSkeleton />
      ) : result.items.length === 0 ? (
        <Card className="mt-6" padding="none">
          <EmptyState
            description={
              requestKey
                ? "Try changing or clearing the current filters."
                : "Manual and AI-detected moments will appear after they are persisted."
            }
            icon={Clapperboard}
            title={requestKey ? "No highlights found" : "No highlights yet"}
          />
        </Card>
      ) : (
        <>
          <p className="mt-6 text-sm font-semibold text-slate-500">
            {result.total} highlights
          </p>
          <div className="mt-3 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {result.items.map((highlight) => (
              <PlatformHighlightCard
                highlight={highlight}
                key={highlight.id}
              />
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

function HighlightSkeleton() {
  return (
    <div className="mt-6 grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <Card key={index}>
          <div className="mb-4 aspect-video animate-pulse rounded-xl bg-slate-100" />
          <LoadingSkeleton lines={3} label="Loading highlight" />
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
