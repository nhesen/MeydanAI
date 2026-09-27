"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Card } from "@/components/ui/Card";
import { AdminGuard } from "@/features/admin/components/AdminGuard";
import { AdminShell } from "@/features/admin/components/AdminShell";
import { PlatformMatchCard } from "@/features/platform/components/PlatformMatchCard";
import { api } from "@/services/api-client";
import type { AdminDashboard } from "@/types/api";

export function AdminDashboardExperience() {
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      await Promise.resolve();
      try {
        const response = await api.getAdminDashboard(controller.signal);
        setData(response.data);
        setFailed(false);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void load();
    return () => controller.abort();
  }, [attempt]);

  return (
    <AdminGuard>
      <AdminShell
        description="System-level counts from persisted data only."
        title="Admin"
      >
        {failed ? (
          <ErrorState
            message="Admin dashboard could not be loaded."
            onRetry={() => setAttempt((current) => current + 1)}
            title="Admin data unavailable"
          />
        ) : !data ? (
          <LoadingSkeleton label="Loading admin dashboard" lines={6} />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <Stat label="Matches" value={data.total_matches} />
              <Stat label="Users" value={data.total_users} />
              <Stat label="Players" value={data.total_players} />
              <Stat label="Teams" value={data.total_teams} />
              <Stat label="Active jobs" value={data.active_jobs} />
              <Stat label="Failed jobs" value={data.failed_jobs} href="/admin/jobs" />
            </div>
            <section className="mt-8">
              <h2 className="font-bold text-slate-950">Recent matches</h2>
              {data.recent_matches.length === 0 ? (
                <p className="mt-3 text-sm text-slate-500">No matches yet.</p>
              ) : (
                <div className="mt-3 grid gap-4 lg:grid-cols-2">
                  {data.recent_matches.map((item) => (
                    <PlatformMatchCard item={item} key={item.match.id} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </AdminShell>
    </AdminGuard>
  );
}

function Stat({
  href,
  label,
  value,
}: {
  href?: string;
  label: string;
  value: number;
}) {
  const content = (
    <Card>
      <p className="text-2xl font-bold tabular-nums text-slate-950">{value}</p>
      <p className="mt-1 text-sm font-semibold text-slate-500">{label}</p>
    </Card>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}
