"use client";

import {
  Activity,
  BarChart3,
  CalendarClock,
  Clapperboard,
  Clock3,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Tabs, type TabItem } from "@/components/ui/Tabs";
import { MATCH_STATUS } from "@/config/match-status";
import { ClipActions } from "@/features/matches/components/ClipActions";
import { MatchHeader } from "@/features/matches/components/MatchHeader";
import { AnalysisQualityPanel } from "@/features/matches/components/AnalysisQualityPanel";
import { PlayerComparison } from "@/features/matches/components/PlayerComparison";
import { PlayerRow } from "@/features/matches/components/PlayerRow";
import { getApiBaseUrl } from "@/lib/env";
import { reviewedEventTitle } from "@/lib/analytics-formatters";
import { ApiError, api } from "@/services/api-client";
import type { MatchDetail, TeamStats } from "@/types/api";

const tabIds = ["overview", "timeline", "stats", "players", "highlights"] as const;
type MatchTab = (typeof tabIds)[number];

interface MatchDetailExperienceProps {
  matchId: string;
}

export function MatchDetailExperience({ matchId }: MatchDetailExperienceProps) {
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab: MatchTab = tabIds.includes(requestedTab as MatchTab)
    ? (requestedTab as MatchTab)
    : "overview";
  const [detail, setDetail] = useState<MatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const [now, setNow] = useState(() => new Date());
  const [error, setError] = useState<{ title: string; message: string } | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function refresh() {
      try {
        const response = await api.getPublicMatchDetail(matchId, controller.signal);
        setDetail(response.data);
        setError(null);
        if (response.data.match.status === "processing" || response.data.match.status === "live") {
          timer = setTimeout(() => void refresh(), 5000);
        }
      } catch (caught: unknown) {
        if (controller.signal.aborted) return;
        setError(
          caught instanceof ApiError && caught.status === 404
            ? {
                title: "Match not found",
                message: "This match may have been removed or the link is incorrect.",
              }
            : {
                title: "Could not load match",
                message: "Check your connection and try again.",
              },
        );
        if (!(caught instanceof ApiError) || caught.status >= 500) {
          timer = setTimeout(() => void refresh(), 10000);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void refresh();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [attempt, matchId]);

  if (loading) return <MatchDetailSkeleton />;

  if (!detail) {
    return (
      <PageContainer className="max-w-4xl">
        <ErrorState
          message={error?.message ?? "The match could not be loaded."}
          onRetry={() => {
            setLoading(true);
            setAttempt((current) => current + 1);
          }}
          title={error?.title ?? "Something went wrong"}
        />
      </PageContainer>
    );
  }

  const tabs: TabItem[] = tabIds.map((id) => ({
    id,
    label: id.charAt(0).toUpperCase() + id.slice(1),
    href: id === "overview" ? `/matches/${matchId}` : `/matches/${matchId}?tab=${id}`,
  }));

  return (
    <PageContainer className="max-w-6xl">
      <MatchHeader match={detail.match} now={now} />
      <AnalysisQualityPanel quality={detail.analysis_quality} />
      <div className="mt-5">
        <Tabs activeId={activeTab} items={tabs} label="Match detail sections" />
      </div>
      <div className="mt-5" role="tabpanel">
        {activeTab === "overview" ? <OverviewTab detail={detail} /> : null}
        {activeTab === "timeline" ? <TimelineTab detail={detail} /> : null}
        {activeTab === "stats" ? <StatsTab detail={detail} /> : null}
        {activeTab === "players" ? (
          <PlayersTab detail={detail} matchId={matchId} />
        ) : null}
        {activeTab === "highlights" ? <HighlightsTab detail={detail} /> : null}
      </div>
    </PageContainer>
  );
}

function OverviewTab({ detail }: { detail: MatchDetail }) {
  const status = MATCH_STATUS[detail.match.status];
  const analyzedPlayers = detail.players.filter((player) => player.analytics_status === "available");
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.8fr)]">
      {detail.match.recording_url ? (
        <Card className="lg:col-span-2">
          <SectionHeader
            description="The uploaded match recording."
            title="Full match"
          />
          <video
            className="mt-4 aspect-video w-full rounded-xl bg-slate-950"
            controls
            playsInline
            preload="metadata"
            src={
              detail.match.recording_url.startsWith("http")
                ? detail.match.recording_url
                : `${getApiBaseUrl()}${detail.match.recording_url}`
            }
          />
          <ClipActions
            src={detail.match.recording_url}
            title={detail.match.title ?? "Match recording"}
          />
        </Card>
      ) : null}
      <Card>
        <SectionHeader
          action={<Badge variant={status.variant}>{status.shortLabel}</Badge>}
          description="A compact view of the real data currently available."
          title="Match overview"
        />
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl bg-subtle p-4">
            <p className="type-stat-label">REGISTERED PLAYERS</p>
            <p className="type-stat-value mt-2 text-slate-950">
              {detail.players.length}
            </p>
          </div>
          <div className="rounded-xl bg-subtle p-4">
            <p className="type-stat-label">REAL TIMELINE EVENTS</p>
            <p className="type-stat-value mt-2 text-slate-950">
              {detail.events.length}
            </p>
          </div>
        </div>
        {analyzedPlayers.length > 0 ? (
          <div className="mt-5 rounded-xl bg-brand-50 p-4">
            <p className="font-semibold text-brand-900">Player analytics are ready</p>
            <p className="mt-1 text-sm leading-6 text-brand-800">
              {analyzedPlayers.length} players have movement and performance results.
            </p>
            <Link className="mt-3 inline-flex min-h-11 items-center text-sm font-semibold text-brand-800 hover:text-brand-950" href={`/matches/${detail.match.id}?tab=players`}>
              View player analytics
            </Link>
          </div>
        ) : detail.match.status === "scheduled" ? (
          <EmptyState
            compact
            description="Player analytics will become available after match data is processed."
            icon={CalendarClock}
            title="Match has not started"
          />
        ) : detail.match.status === "processing" ? (
          <EmptyState
            compact
            description="Movement and performance data is being prepared."
            icon={Activity}
            title="Analytics are processing"
          />
        ) : (
          <EmptyState
            compact
            description="Distance, speed and rating data has not been recorded for this match."
            icon={BarChart3}
            title="Player analytics are not available yet"
          />
        )}
      </Card>
      <Card>
        <SectionHeader title="Team comparison" />
        <TeamComparison
          stats={detail.team_stats}
          teams={detail.match.teams}
        />
      </Card>
    </div>
  );
}

function TimelineTab({ detail }: { detail: MatchDetail }) {
  return (
    <Card>
      <SectionHeader
        description="Recorded match events in chronological order. AI suggestions require review."
        title="Timeline"
      />
      {detail.events.length === 0 ? (
        <EmptyState
          description="Goals, substitutions, jersey changes and important moments will appear here when recorded."
          icon={Clock3}
          title="No timeline events yet"
        />
      ) : (
        <ol className="mt-6 space-y-1">
          {detail.events.filter((event) => event.review_status !== "rejected").map((event) => (
            <li
              className="grid grid-cols-[3rem_1px_minmax(0,1fr)] gap-3"
              key={event.id}
            >
              <span className="pt-3 text-right text-xs font-bold tabular-nums text-brand-700">
                {event.minute !== null ? `${event.minute}′` : "—"}
              </span>
              <span className="bg-border" aria-hidden="true" />
              <div className="pb-5 pt-2">
                <p className="text-sm font-semibold text-slate-950">{reviewedEventTitle(event.title, event.review_status)}</p>
                {event.review_status ? <div className="mt-2"><Badge variant={event.review_status === "confirmed" ? "success" : "warning"}>{event.review_status === "confirmed" ? "Organizer confirmed" : "AI suggestion · needs review"}</Badge></div> : null}
                {event.description ? (
                  <p className="mt-1 text-sm text-slate-600">{event.description}</p>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function StatsTab({ detail }: { detail: MatchDetail }) {
  return (
    <Card>
      <SectionHeader
        description="Only metrics calculated from real match data are displayed."
        title="Team stats"
      />
      <TeamComparison stats={detail.team_stats} teams={detail.match.teams} large />
    </Card>
  );
}

function PlayersTab({
  detail,
  matchId,
}: {
  detail: MatchDetail;
  matchId: string;
}) {
  if (detail.players.length === 0) {
    return (
      <Card>
        <EmptyState
          description="Players will appear after they join the match or an organizer assigns them."
          icon={UsersRound}
          title="No players in this match"
        />
      </Card>
    );
  }
  return (
    <div>
      <PlayerComparison matchId={matchId} players={detail.players} />
      <div className="grid gap-5 lg:grid-cols-2">
        {detail.match.teams.map((team) => {
          const players = detail.players.filter(
            (player) => player.team.id === team.id,
          );
          return (
            <Card key={team.id}>
              <SectionHeader
                action={<Badge>{players.length} players</Badge>}
                title={team.name}
              />
              {players.length === 0 ? (
                <p className="mt-5 rounded-xl bg-subtle p-4 text-sm text-slate-600">
                  No players have joined this team.
                </p>
              ) : (
                <div className="mt-3">
                  {players.map((player) => (
                    <PlayerRow
                      key={player.id}
                      matchId={matchId}
                      player={player}
                    />
                  ))}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function videoOffset(startsAt: string, occurredAt: string | null) {
  if (!occurredAt) return "";
  const elapsed = Math.max(
    0,
    Math.round((new Date(occurredAt).getTime() - new Date(startsAt).getTime()) / 1000),
  );
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function HighlightsTab({ detail }: { detail: MatchDetail }) {
  const [filter, setFilter] = useState("All");
  const filters = ["All", "Goals", "Top Runs", "Key Moments"] as const;
  const visible = detail.highlights.filter((item) => {
    if (item.review_status === "rejected") return false;
    if (filter === "Goals") return item.highlight_type === "goal";
    if (filter === "Top Runs") {
      return item.highlight_type === "top_run" || item.highlight_type === "sprint";
    }
    if (filter === "Key Moments") {
      return (
        item.highlight_type === "key_moment" ||
        item.highlight_type === "ai_detected"
      );
    }
    return true;
  });
  const count = (name: (typeof filters)[number]) =>
    detail.highlights.filter((item) => {
      if (item.review_status === "rejected") return false;
      if (name === "Goals") return item.highlight_type === "goal";
      if (name === "Top Runs") {
        return item.highlight_type === "top_run" || item.highlight_type === "sprint";
      }
      if (name === "Key Moments") {
        return (
          item.highlight_type === "key_moment" ||
          item.highlight_type === "ai_detected"
        );
      }
      return true;
    }).length;

  return (
    <Card>
      <SectionHeader
        description="Suggested moments from the match video. Review clips to confirm the action."
        title="Highlights"
      />
      <div className="mt-5 flex gap-2 overflow-x-auto pb-1">
        {filters.map((name) => (
          <button
            className={`h-9 shrink-0 rounded-full px-4 text-sm font-semibold ${
              filter === name
                ? "bg-brand-100 text-brand-800"
                : "bg-subtle text-slate-500"
            }`}
            disabled={count(name) === 0}
            key={name}
            onClick={() => setFilter(name)}
            type="button"
          >
            {name}
          </button>
        ))}
      </div>
      {visible.length === 0 ? (
        <EmptyState
          description="No highlights are available for this match yet."
          icon={Clapperboard}
          title="No highlights yet"
        />
      ) : (
        <ul className="mt-5 divide-y divide-border">
          {visible.map((item) => (
            <li className="py-3" key={item.id}>
              {item.video_url ? (
                <video
                  className="mb-3 aspect-video w-full rounded-xl bg-slate-950"
                  controls
                  playsInline
                  preload="metadata"
                  src={
                    item.video_url.startsWith("http")
                      ? item.video_url
                      : `${getApiBaseUrl()}${item.video_url}`
                  }
                />
              ) : null}
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="font-semibold text-slate-950">{reviewedEventTitle(item.title, item.review_status)}</p>
                  <div className="mt-1"><Badge variant={item.review_status === "confirmed" ? "success" : "warning"}>{item.review_status === "confirmed" ? "Organizer confirmed" : "Needs review"}</Badge></div>
                  <p className="text-sm text-slate-500">
                    {item.highlight_type.replaceAll("_", " ")}
                  </p>
                </div>
                <span className="shrink-0 text-sm font-semibold tabular-nums text-slate-500">
                  {videoOffset(detail.match.starts_at, item.occurred_at)}
                </span>
              </div>
              {item.video_url ? <ClipActions src={item.video_url} title={item.title} /> : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function TeamComparison({
  large = false,
  stats,
  teams,
}: {
  large?: boolean;
  stats: TeamStats[] | null;
  teams: MatchDetail["match"]["teams"];
}) {
  if (!stats) {
    return (
      <EmptyState
        compact={!large}
        description="Distance, speed, sprint and active-time metrics have not been calculated."
        icon={BarChart3}
        title="Team analytics are unavailable"
      />
    );
  }
  const metrics: Array<{
    label: string;
    value: (stat: TeamStats) => string;
  }> = [
    {
      label: "Total distance",
      value: (stat) =>
        stat.total_distance_m === null
          ? "N/A"
          : `${(stat.total_distance_m / 1000).toFixed(2)} km`,
    },
    {
      label: "Average speed",
      value: (stat) =>
        stat.average_speed_kmh === null
          ? "N/A"
          : `${stat.average_speed_kmh.toFixed(1)} km/h`,
    },
    {
      label: "Maximum speed",
      value: (stat) =>
        stat.maximum_speed_kmh === null
          ? "N/A"
          : `${stat.maximum_speed_kmh.toFixed(1)} km/h`,
    },
    {
      label: "Goals",
      value: (stat) => stat.goals?.toString() ?? "N/A",
    },
    {
      label: "Shots",
      value: (stat) => stat.shots?.toString() ?? "N/A",
    },
    {
      label: "Shots on target",
      value: (stat) => stat.shots_on_target?.toString() ?? "N/A",
    },
    {
      label: "xG",
      value: (stat) => (stat.xg == null ? "N/A" : stat.xg.toFixed(2)),
    },
    {
      label: "Big chances",
      value: (stat) => stat.big_chances?.toString() ?? "N/A",
    },
    {
      label: "Saves",
      value: (stat) => stat.saves?.toString() ?? "N/A",
    },
    {
      label: "Corners",
      value: (stat) => stat.corners?.toString() ?? "N/A",
    },
    {
      label: "Goal kicks",
      value: (stat) => stat.goal_kicks?.toString() ?? "N/A",
    },
    {
      label: "Posts",
      value: (stat) => stat.woodwork?.toString() ?? "N/A",
    },
    {
      label: "Passes",
      value: (stat) =>
        stat.passes == null
          ? "N/A"
          : `${stat.accurate_passes ?? 0}/${stat.passes}`,
    },
    {
      label: "Tackles",
      value: (stat) => stat.tackles?.toString() ?? "N/A",
    },
    {
      label: "Interceptions",
      value: (stat) => stat.interceptions?.toString() ?? "N/A",
    },
    {
      label: "Fouls",
      value: () => "N/A",
    },
    {
      label: "Sprints",
      value: (stat) => stat.sprint_count?.toString() ?? "N/A",
    },
  ];
  const firstStats = stats.find((item) => item.team_id === teams[0]?.id);
  const secondStats = stats.find((item) => item.team_id === teams[1]?.id);
  const visible = metrics.filter((metric) => {
    const left = firstStats ? metric.value(firstStats) : "N/A";
    const right = secondStats ? metric.value(secondStats) : "N/A";
    return left !== "N/A" || right !== "N/A";
  });
  return (
    <div className="mt-5">
      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 text-xs font-bold text-slate-500">
        <span>{teams[0]?.name}</span>
        <span />
        <span className="text-right">{teams[1]?.name}</span>
      </div>
      {visible.map((metric) => (
        <div
          className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-border py-4 last:border-0"
          key={metric.label}
        >
          <span className="text-sm font-semibold text-slate-950">
            {firstStats ? metric.value(firstStats) : "N/A"}
          </span>
          <span className="text-xs text-slate-500">{metric.label}</span>
          <span className="text-right text-sm font-semibold text-slate-950">
            {secondStats ? metric.value(secondStats) : "N/A"}
          </span>
        </div>
      ))}
    </div>
  );
}

function MatchDetailSkeleton() {
  return (
    <PageContainer className="max-w-6xl">
      <Card>
        <div className="grid grid-cols-3 items-center gap-5 py-6">
          <LoadingSkeleton lines={2} label="Loading home team" />
          <div className="h-16 animate-pulse rounded-xl bg-subtle" />
          <LoadingSkeleton lines={2} label="Loading away team" />
        </div>
      </Card>
      <Card className="mt-5">
        <LoadingSkeleton lines={7} label="Loading match detail" />
      </Card>
    </PageContainer>
  );
}
