"use client";

import {
  BarChart3,
  Gauge,
  Medal,
  Route,
  Zap,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import {
  updateQueryHref,
} from "@/features/platform/components/DirectoryControls";
import {
  formatCount,
  formatDistance,
  formatRating,
  formatSpeed,
} from "@/lib/analytics-formatters";
import { api } from "@/services/api-client";
import type {
  AnalyticsLeaderboards,
  LeaderboardEntry,
  TeamAnalyticsSummary,
  TeamDirectoryItem,
} from "@/types/api";

export function AnalyticsExperience() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestKey = searchParams.toString();
  const [data, setData] = useState<AnalyticsLeaderboards | null>(null);
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
    async function loadAnalytics() {
      await Promise.resolve();
      try {
        const response = await api.getAnalytics(
          {
            team_id: searchParams.get("team") ?? undefined,
            date_from: searchParams.get("from") ?? undefined,
            date_to: searchParams.get("to") ?? undefined,
            minimum_matches: positiveNumber(searchParams.get("minimum")),
          },
          controller.signal,
        );
        setData(response.data);
        setFailed(false);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void loadAnalytics();
    return () => controller.abort();
  }, [attempt, requestKey, searchParams]);

  const hasRankings = data
    ? [
        data.rating_leaders,
        data.distance_leaders,
        data.speed_leaders,
        data.sprint_leaders,
      ].some((items) => items.length > 0)
    : false;

  return (
    <PageContainer className="max-w-7xl">
      <PageHeader
        description="Separate rankings from real persisted match analytics."
        eyebrow="Platform insights"
        title="Analytics"
      />
      <Card className="mt-6 sm:mt-8" padding="sm">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <select
            aria-label="Filter analytics by team"
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
            aria-label="Analytics from date"
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
            aria-label="Analytics to date"
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
          <select
            aria-label="Minimum match count"
            className={filterClass}
            onChange={(event) =>
              router.push(
                updateQueryHref(pathname, searchParams, {
                  minimum: event.target.value,
                }),
              )
            }
            value={searchParams.get("minimum") ?? "1"}
          >
            <option value="1">1+ matches</option>
            <option value="3">3+ matches</option>
            <option value="5">5+ matches</option>
            <option value="10">10+ matches</option>
          </select>
        </div>
      </Card>

      {failed ? (
        <div className="mt-6">
          <ErrorState
            message="Analytics rankings could not be loaded."
            onRetry={() => setAttempt((current) => current + 1)}
            title="Analytics unavailable"
          />
        </div>
      ) : !data ? (
        <AnalyticsSkeleton />
      ) : !hasRankings && data.team_analytics.length === 0 ? (
        <Card className="mt-6" padding="none">
          <EmptyState
            description="Rankings appear only after real player analytics have been persisted."
            icon={BarChart3}
            title="No analytics available"
          />
        </Card>
      ) : (
        <>
          <div className="mt-8 grid gap-5 md:grid-cols-2">
            <Leaderboard
              entries={data.rating_leaders}
              format={formatRating}
              icon={Medal}
              title="Rating leaders"
            />
            <Leaderboard
              entries={data.distance_leaders}
              format={formatDistance}
              icon={Route}
              title="Distance leaders"
            />
            <Leaderboard
              entries={data.speed_leaders}
              format={formatSpeed}
              icon={Gauge}
              title="Speed leaders"
            />
            <Leaderboard
              entries={data.sprint_leaders}
              format={(value) => formatCount(value)}
              icon={Zap}
              title="Sprint leaders"
            />
          </div>
          <section className="mt-8" aria-labelledby="team-analytics">
            <SectionHeader
              description="Aggregates include only metrics that were actually persisted."
              id="team-analytics"
              title="Team analytics"
            />
            {data.team_analytics.length ? (
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                {data.team_analytics.map((team) => (
                  <TeamAnalyticsCard key={team.team_id} team={team} />
                ))}
              </div>
            ) : (
              <Card className="mt-4" padding="none">
                <EmptyState
                  compact
                  description="Team aggregates are not available for this filter."
                  icon={BarChart3}
                  title="No team analytics"
                />
              </Card>
            )}
          </section>
        </>
      )}
    </PageContainer>
  );
}

function Leaderboard({
  entries,
  format,
  icon: Icon,
  title,
}: {
  entries: LeaderboardEntry[];
  format: (value: number) => string;
  icon: LucideIcon;
  title: string;
}) {
  return (
    <Card padding="none">
      <div className="flex items-center gap-2 border-b border-border px-5 py-4">
        <Icon className="size-5 text-brand-700" aria-hidden="true" />
        <h2 className="font-bold text-slate-950">{title}</h2>
      </div>
      {entries.length ? (
        <ol className="divide-y divide-border">
          {entries.map((entry, index) => (
            <li key={entry.player_id}>
              <Link
                className="flex min-h-16 items-center gap-3 px-5 py-3 hover:bg-subtle/60 focus-visible:outline-2 focus-visible:outline-brand-700"
                href={`/players/${entry.player_id}`}
              >
                <span className="w-5 text-sm font-bold text-slate-400">
                  {index + 1}
                </span>
                <Avatar className="size-9 text-xs" name={entry.display_name} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-slate-950">
                    {entry.display_name}
                  </span>
                  <span className="text-xs text-slate-500">
                    {entry.match_count} matches
                  </span>
                </span>
                <span className="text-sm font-bold tabular-nums text-brand-800">
                  {format(entry.value)}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState
          compact
          description="No qualifying metric values."
          title="No ranking data"
        />
      )}
    </Card>
  );
}

function TeamAnalyticsCard({ team }: { team: TeamAnalyticsSummary }) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <Link
          className="truncate font-bold text-slate-950 hover:text-brand-800"
          href={`/teams/${team.team_id}`}
        >
          {team.team_name}
        </Link>
        <span className="text-xs font-semibold text-slate-500">
          {team.match_count} matches
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <TeamMetric
          label="Total distance"
          value={formatDistance(team.total_distance_m)}
        />
        <TeamMetric
          label="Average speed"
          value={formatSpeed(team.average_speed_kmh)}
        />
        <TeamMetric
          label="Maximum speed"
          value={formatSpeed(team.maximum_speed_kmh)}
        />
        <TeamMetric
          label="Sprints"
          value={formatCount(team.sprint_count)}
        />
      </div>
    </Card>
  );
}

function TeamMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-subtle p-3">
      <p className="text-sm font-bold tabular-nums text-slate-950">{value}</p>
      <p className="mt-1 text-xs font-semibold text-slate-500">{label}</p>
    </div>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="mt-8 grid gap-5 md:grid-cols-2">
      {Array.from({ length: 4 }, (_, index) => (
        <Card key={index}>
          <LoadingSkeleton lines={6} label="Loading analytics ranking" />
        </Card>
      ))}
    </div>
  );
}

function positiveNumber(value: string | null) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
}

const filterClass =
  "h-11 min-w-0 rounded-xl border border-border bg-white px-3 text-sm text-slate-700 focus:border-brand-600 focus:outline-2 focus:outline-brand-600";
