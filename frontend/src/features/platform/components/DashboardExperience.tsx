"use client";

import {
  Activity,
  BarChart3,
  CalendarClock,
  CalendarDays,
  CheckCircle2,
  Clapperboard,
  Shield,
  UsersRound,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { Avatar } from "@/components/ui/Avatar";
import { Card } from "@/components/ui/Card";
import { PlatformHighlightCard } from "@/features/platform/components/PlatformHighlightCard";
import { PlatformMatchCard } from "@/features/platform/components/PlatformMatchCard";
import { formatRating } from "@/lib/analytics-formatters";
import { api } from "@/services/api-client";
import type { DashboardData } from "@/types/api";

export function DashboardExperience() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      await Promise.resolve();
      if (controller.signal.aborted) return;
      try {
        const response = await api.getDashboard(controller.signal);
        setData(response.data);
      } catch {
        if (!controller.signal.aborted) setData(null);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [attempt]);

  if (loading) return <DashboardSkeleton />;
  if (!data) {
    return (
      <PageContainer>
        <ErrorState
          message="The platform overview could not be loaded. Check your connection and try again."
          onRetry={() => {
            setLoading(true);
            setAttempt((current) => current + 1);
          }}
          title="Dashboard unavailable"
        />
      </PageContainer>
    );
  }

  const quickStats = [
    { label: "Total matches", value: data.quick_stats.total_matches, icon: CalendarDays },
    {
      label: "Completed",
      value: data.quick_stats.completed_matches,
      icon: CheckCircle2,
    },
    { label: "Players", value: data.quick_stats.total_players, icon: UsersRound },
    { label: "Teams", value: data.quick_stats.total_teams, icon: Shield },
    {
      label: "Processed",
      value: data.quick_stats.processed_matches,
      icon: BarChart3,
    },
  ];

  return (
    <PageContainer className="max-w-7xl">
      <PageHeader
        action={
          <Link
            className="inline-flex h-11 items-center justify-center rounded-xl bg-brand-700 px-4 text-sm font-semibold text-white hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700"
            href="/matches/new"
          >
            Create match
          </Link>
        }
        description="Matches, players, processing and verified analytics in one place."
        eyebrow="Football analytics"
        title="MeydanAI dashboard"
      />

      <section
        aria-label="Platform summary"
        className="mt-6 grid grid-cols-2 gap-3 sm:mt-8 lg:grid-cols-5"
      >
        {quickStats.map(({ icon: Icon, label, value }) => (
          <Card key={label} padding="sm">
            <Icon className="size-4 text-brand-700" aria-hidden="true" />
            <p className="mt-4 text-2xl font-bold tabular-nums text-slate-950">
              {value}
            </p>
            <p className="mt-1 text-xs font-semibold text-slate-500">{label}</p>
          </Card>
        ))}
      </section>

      <div className="mt-8 grid gap-8 xl:grid-cols-[minmax(0,1.45fr)_minmax(19rem,0.7fr)]">
        <section aria-labelledby="recent-matches">
          <SectionHeader
            action={<SectionLink href="/matches">View all</SectionLink>}
            id="recent-matches"
            title="Recent matches"
          />
          {data.recent_matches.length ? (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {data.recent_matches.map((item) => (
                <PlatformMatchCard item={item} key={item.match.id} />
              ))}
            </div>
          ) : (
            <Card className="mt-4" padding="none">
              <EmptyState
                compact
                description="Completed matches will appear here."
                icon={CalendarClock}
                title="No recent matches"
              />
            </Card>
          )}
        </section>

        <section aria-labelledby="upcoming-matches">
          <SectionHeader id="upcoming-matches" title="Upcoming" />
          {data.upcoming_matches.length ? (
            <div className="mt-4 space-y-3">
              {data.upcoming_matches.slice(0, 3).map((item) => (
                <PlatformMatchCard item={item} key={item.match.id} />
              ))}
            </div>
          ) : (
            <Card className="mt-4" padding="none">
              <EmptyState
                compact
                description="Scheduled matches will appear here."
                icon={CalendarDays}
                title="Nothing scheduled"
              />
            </Card>
          )}
        </section>
      </div>

      <section className="mt-8" aria-labelledby="processing-matches">
        <SectionHeader
          description="Public match lifecycle status; private job details remain organizer-protected."
          id="processing-matches"
          title="Processing matches"
        />
        {data.processing_matches.length ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {data.processing_matches.map((item) => (
              <PlatformMatchCard item={item} key={item.match.id} />
            ))}
          </div>
        ) : (
          <Card className="mt-4" padding="none">
            <EmptyState
              compact
              description="No matches are currently processing."
              icon={Activity}
              title="Processing queue is clear"
            />
          </Card>
        )}
      </section>

      <div className="mt-8 grid gap-8 xl:grid-cols-[minmax(18rem,0.7fr)_minmax(0,1.4fr)]">
        <section aria-labelledby="top-players">
          <SectionHeader
            action={<SectionLink href="/analytics">Rankings</SectionLink>}
            id="top-players"
            title="Top rated players"
          />
          <Card className="mt-4" padding="none">
            {data.top_players.length ? (
              <ol className="divide-y divide-border">
                {data.top_players.map((player, index) => (
                  <li key={player.player_id}>
                    <Link
                      className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-subtle/60 focus-visible:outline-2 focus-visible:outline-brand-700"
                      href={`/players/${player.player_id}`}
                    >
                      <span className="w-5 text-sm font-bold text-slate-400">
                        {index + 1}
                      </span>
                      <Avatar
                        className="size-9 text-xs"
                        name={player.display_name}
                      />
                      <span className="min-w-0 flex-1 truncate text-sm font-semibold text-slate-950">
                        {player.display_name}
                      </span>
                      <span className="font-bold tabular-nums text-brand-800">
                        {formatRating(player.value)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState
                compact
                description="Rated match performances are not available yet."
                icon={BarChart3}
                title="No player rankings"
              />
            )}
          </Card>
        </section>

        <section aria-labelledby="latest-highlights">
          <SectionHeader
            action={<SectionLink href="/highlights">View all</SectionLink>}
            id="latest-highlights"
            title="Latest highlights"
          />
          {data.latest_highlights.length ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {data.latest_highlights.map((highlight) => (
                <PlatformHighlightCard
                  highlight={highlight}
                  key={highlight.id}
                />
              ))}
            </div>
          ) : (
            <Card className="mt-4" padding="none">
              <EmptyState
                compact
                description="Verified manual or AI-generated highlights will appear here."
                icon={Clapperboard}
                title="No highlights yet"
              />
            </Card>
          )}
        </section>
      </div>
    </PageContainer>
  );
}

function SectionLink({ href, children }: { href: string; children: string }) {
  return (
    <Link
      className="inline-flex min-h-11 items-center text-sm font-semibold text-brand-700 hover:text-brand-900"
      href={href}
    >
      {children}
    </Link>
  );
}

function DashboardSkeleton() {
  return (
    <PageContainer className="max-w-7xl">
      <LoadingSkeleton lines={3} label="Loading dashboard header" />
      <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, index) => (
          <Card className="h-28 animate-pulse bg-subtle" key={index} />
        ))}
      </div>
      <div className="mt-8 grid gap-5 md:grid-cols-2">
        {Array.from({ length: 4 }, (_, index) => (
          <Card className="h-48 animate-pulse bg-subtle" key={index} />
        ))}
      </div>
    </PageContainer>
  );
}
