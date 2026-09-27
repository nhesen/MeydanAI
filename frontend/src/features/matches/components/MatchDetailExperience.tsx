"use client";

import {
  Activity,
  BarChart3,
  CalendarClock,
  Clapperboard,
  Clock3,
  UsersRound,
} from "lucide-react";
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
import { MatchHeader } from "@/features/matches/components/MatchHeader";
import { PlayerRow } from "@/features/matches/components/PlayerRow";
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
    api
      .getPublicMatchDetail(matchId, controller.signal)
      .then((response) => {
        setDetail(response.data);
        setError(null);
      })
      .catch((caught: unknown) => {
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
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
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
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.8fr)]">
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
        {detail.match.status === "scheduled" ? (
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
        description="Verified match events in chronological order."
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
          {detail.events.map((event) => (
            <li
              className="grid grid-cols-[3rem_1px_minmax(0,1fr)] gap-3"
              key={event.id}
            >
              <span className="pt-3 text-right text-xs font-bold tabular-nums text-brand-700">
                {event.minute !== null ? `${event.minute}′` : "—"}
              </span>
              <span className="bg-border" aria-hidden="true" />
              <div className="pb-5 pt-2">
                <p className="text-sm font-semibold text-slate-950">{event.title}</p>
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
    <div className="grid gap-5 lg:grid-cols-2">
      {detail.match.teams.map((team) => {
        const players = detail.players.filter((player) => player.team.id === team.id);
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
                  <PlayerRow key={player.id} matchId={matchId} player={player} />
                ))}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function HighlightsTab({ detail }: { detail: MatchDetail }) {
  const filters = ["All", "Goals", "Top Runs", "Key Moments"];
  return (
    <Card>
      <SectionHeader
        description="Manual and future AI-assisted moments will be organized here."
        title="Highlights"
      />
      <div className="mt-5 flex gap-2 overflow-x-auto pb-1">
        {filters.map((filter, index) => (
          <button
            className={`h-9 shrink-0 rounded-full px-4 text-sm font-semibold ${
              index === 0
                ? "bg-brand-100 text-brand-800"
                : "bg-subtle text-slate-500"
            }`}
            disabled={index !== 0 || detail.highlights.length === 0}
            key={filter}
            type="button"
          >
            {filter}
          </button>
        ))}
      </div>
      <EmptyState
        description="No highlights are available for this match yet."
        icon={Clapperboard}
        title="No highlights yet"
      />
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
      label: "Sprints",
      value: (stat) => stat.sprint_count?.toString() ?? "N/A",
    },
  ];
  const firstStats = stats.find((item) => item.team_id === teams[0]?.id);
  const secondStats = stats.find((item) => item.team_id === teams[1]?.id);
  return (
    <div className="mt-5">
      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 text-xs font-bold text-slate-500">
        <span>{teams[0]?.name}</span>
        <span />
        <span className="text-right">{teams[1]?.name}</span>
      </div>
      {metrics.map((metric) => (
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
