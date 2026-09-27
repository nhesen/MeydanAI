"use client";

import { ArrowLeft, BarChart3 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  formatDistance,
  formatRating,
  formatSpeed,
} from "@/lib/analytics-formatters";
import { ApiError, api } from "@/services/api-client";
import type { GlobalPlayerProfile as Profile } from "@/types/api";

export function GlobalPlayerProfile({ playerId }: { playerId: string }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      await Promise.resolve();
      try {
        const response = await api.getPlayerProfile(playerId, controller.signal);
        setProfile(response.data);
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
  }, [playerId]);

  if (loading) {
    return (
      <PageContainer className="max-w-5xl">
        <Card>
          <LoadingSkeleton lines={6} label="Loading player profile" />
        </Card>
      </PageContainer>
    );
  }
  if (!profile) {
    return (
      <PageContainer className="max-w-5xl">
        <ErrorState
          message={
            failed
              ? "The player profile could not be loaded."
              : "This player profile does not exist."
          }
          title={failed ? "Profile unavailable" : "Player not found"}
        />
      </PageContainer>
    );
  }

  return (
    <PageContainer className="max-w-5xl">
      <Link
        className="mb-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-slate-600 hover:text-brand-800"
        href="/players"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to players
      </Link>
      <Card padding="lg">
        <div className="flex items-center gap-4">
          <Avatar className="size-16 text-lg" name={profile.display_name} />
          <div className="min-w-0">
            <Badge variant={profile.is_temporary ? "neutral" : "brand"}>
              {profile.is_temporary ? "Match-created identity" : "Player profile"}
            </Badge>
            <h1 className="mt-3 break-words text-2xl font-bold text-slate-950 sm:text-3xl">
              {profile.display_name}
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Global identity · jerseys remain match-specific
            </p>
          </div>
        </div>
      </Card>

      <section className="mt-6" aria-labelledby="recent-performances">
        <h2 className="type-section-title text-slate-950" id="recent-performances">
          Recent match performances
        </h2>
        {profile.recent_performances.length ? (
          <div className="mt-4 space-y-3">
            {profile.recent_performances.map((performance) => (
              <Link
                className="block rounded-2xl border border-border bg-white p-4 shadow-card hover:border-brand-200 focus-visible:outline-2 focus-visible:outline-brand-700"
                href={`/matches/${performance.match_id}/players/${profile.id}`}
                key={performance.match_id}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-bold text-slate-950">
                      {performance.match_title ?? performance.venue_name}
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
                      {performance.team.name} ·{" "}
                      {new Intl.DateTimeFormat("en", {
                        dateStyle: "medium",
                      }).format(new Date(performance.starts_at))}
                    </p>
                  </div>
                  <Badge variant={performance.rating === null ? "neutral" : "brand"}>
                    Rating {formatRating(performance.rating)}
                  </Badge>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-subtle p-3">
                  <Metric
                    label="Distance"
                    value={formatDistance(performance.distance_m)}
                  />
                  <Metric
                    label="Max speed"
                    value={formatSpeed(performance.max_speed_kmh)}
                  />
                  <Metric
                    label="Sprints"
                    value={performance.sprint_count?.toString() ?? "N/A"}
                  />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <Card className="mt-4" padding="none">
            <EmptyState
              description="No real match analytics are available for this player."
              icon={BarChart3}
              title="No performance history"
            />
          </Card>
        )}
      </section>
    </PageContainer>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <p className="text-sm font-bold tabular-nums text-slate-950">{value}</p>
      <p className="mt-1 text-xs font-semibold text-slate-500">{label}</p>
    </div>
  );
}
