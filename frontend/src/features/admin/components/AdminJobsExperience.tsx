"use client";

import { useEffect, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { AdminGuard } from "@/features/admin/components/AdminGuard";
import { AdminShell } from "@/features/admin/components/AdminShell";
import { api } from "@/services/api-client";
import type { ProcessingJob } from "@/types/api";

export function AdminJobsExperience() {
  const [jobs, setJobs] = useState<ProcessingJob[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [pending, setPending] = useState<ProcessingJob | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    await Promise.resolve();
    try {
      const response = await api.getAdminJobs({ page_size: 30 });
      setJobs(response.data.items);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }

  useEffect(() => {
    async function initialize() {
      await Promise.resolve();
      try {
        const response = await api.getAdminJobs({ page_size: 30 });
        setJobs(response.data.items);
        setFailed(false);
      } catch {
        setFailed(true);
      }
    }
    void initialize();
  }, []);

  async function retry() {
    if (!pending) return;
    setBusy(true);
    try {
      await api.retryAdminJob(pending.id);
      setPending(null);
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminGuard>
      <AdminShell
        description="Retry only failed jobs. Completed jobs stay closed."
        title="Processing jobs"
      >
        {failed ? (
          <ErrorState message="Jobs could not be loaded." onRetry={() => void load()} title="Jobs unavailable" />
        ) : jobs === null ? (
          <LoadingSkeleton label="Loading jobs" lines={5} />
        ) : jobs.length === 0 ? (
          <p className="text-sm text-slate-500">No processing jobs yet.</p>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <Card key={job.id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-950">Job {job.id.slice(0, 8)}</p>
                    <p className="mt-1 text-sm text-slate-500">
                      {job.stage.replaceAll("_", " ")} · match {job.match_id.slice(0, 8)}
                    </p>
                    {job.error_message ? (
                      <p className="mt-2 text-sm text-danger-700">{job.error_message}</p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge>{job.status}</Badge>
                    {job.status === "failed" ? (
                      <Button onClick={() => setPending(job)} size="sm">
                        Retry
                      </Button>
                    ) : null}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
        <ConfirmDialog
          busy={busy}
          confirmLabel="Retry job"
          description="A new queued job will be created from the failed source. The original job stays in history."
          onCancel={() => setPending(null)}
          onConfirm={() => void retry()}
          open={pending !== null}
          title="Retry failed job"
        />
      </AdminShell>
    </AdminGuard>
  );
}
