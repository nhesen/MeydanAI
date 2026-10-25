"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RefreshCw,
  Upload,
  Video,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import {
  PROCESSING_STAGE_LABELS,
  PROCESSING_STATUS,
} from "@/config/processing";
import { ApiError, api } from "@/services/api-client";
import { PitchCalibrationEditor } from "@/features/matches/components/PitchCalibrationEditor";
import { RELATIVE_CALIBRATION } from "@/lib/calibration";
import type { ProcessingJob, UploadCalibrationConfig } from "@/types/api";

interface ProcessingJobsPanelProps {
  matchId: string;
  organizerToken?: string | null;
  onCompleted?: () => void;
}

export function ProcessingJobsPanel({
  matchId,
  organizerToken,
  onCompleted,
}: ProcessingJobsPanelProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadController = useRef<AbortController | null>(null);
  const previousJobs = useRef<ProcessingJob[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [calibration, setCalibration] = useState<UploadCalibrationConfig | null>(RELATIVE_CALIBRATION);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      const response = await api.getProcessingJobs(
        matchId,
        organizerToken,
        signal,
      );
      setJobs(response.data);
      setRefreshError(null);
    },
    [matchId, organizerToken],
  );

  useEffect(() => {
    const controller = new AbortController();
    async function initialize() {
      await Promise.resolve();
      if (controller.signal.aborted) return;
      try {
        await load(controller.signal);
      } catch {
        if (!controller.signal.aborted) {
          setRefreshError("Processing jobs could not be loaded. Refresh to try again.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void initialize();
    return () => controller.abort();
  }, [load]);

  useEffect(() => () => uploadController.current?.abort(), []);

  useEffect(() => {
    const completed = jobs.some((job) => job.status === "completed" && previousJobs.current.some(
      (previous) => previous.id === job.id && (previous.status === "queued" || previous.status === "processing"),
    ));
    previousJobs.current = jobs;
    if (completed) onCompleted?.();
  }, [jobs, onCompleted]);

  const hasActiveJob = jobs.some(
    (job) => job.status === "queued" || job.status === "processing",
  );

  useEffect(() => {
    if (!hasActiveJob) return;
    const controller = new AbortController();
    let pending = false;
    const timer = window.setInterval(async () => {
      if (pending) return;
      pending = true;
      try {
        await load(controller.signal);
      } catch {
        if (!controller.signal.aborted) {
          setRefreshError("Processing status could not be refreshed. Retrying automatically.");
        }
      } finally {
        pending = false;
      }
    }, 5000);
    return () => {
      window.clearInterval(timer);
      controller.abort();
    };
  }, [hasActiveJob, load]);

  async function refreshJobs() {
    setRefreshing(true);
    try {
      await load();
    } catch {
      setRefreshError("Processing jobs could not be refreshed. Check your connection and try again.");
    } finally {
      setRefreshing(false);
    }
  }

  function selectFile(selected: File | null) {
    setError(null);
    setCalibration(RELATIVE_CALIBRATION);
    if (selected && (!/\.(mp4|m4v|mov|webm)$/i.test(selected.name) || selected.size === 0)) {
      setError("Select a non-empty MP4, MOV, or WebM video.");
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setFile(selected);
  }

  async function uploadVideo() {
    if (!file || !calibration || uploading || hasActiveJob || busyJobId) return;
    const controller = new AbortController();
    uploadController.current = controller;
    setUploading(true);
    setUploadProgress(0);
    setError(null);
    try {
      const response = await api.createProcessingJob(matchId, organizerToken, file, {
        signal: controller.signal,
        onProgress: setUploadProgress,
        calibration,
      });
      setJobs((current) => [response.data, ...current.filter((job) => job.id !== response.data.id)]);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
    } catch (caught: unknown) {
      if (!(caught instanceof DOMException && caught.name === "AbortError")) {
        setError(uploadErrorMessage(caught));
      }
    } finally {
      uploadController.current = null;
      setUploading(false);
    }
  }

  async function retryJob(jobId: string) {
    if (busyJobId || hasActiveJob || uploading) return;
    setBusyJobId(jobId);
    setError(null);
    try {
      const response = await api.retryProcessingJob(jobId, organizerToken);
      setJobs((current) => [response.data, ...current.filter((job) => job.id !== response.data.id)]);
    } catch {
      setError("The failed processing job could not be retried. Refresh its status and try again.");
    } finally {
      setBusyJobId(null);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Badge variant="info">Analytics processing</Badge>
            <h2 className="mt-3 text-lg font-semibold text-slate-950">
              Upload match video
            </h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
              Upload an MP4, MOV, or WebM match video to track player movement.
              Detected players, teams and events are estimates and need review.
              Temporary player labels do not confirm a person&apos;s identity.
            </p>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
              Distance and speed require valid pitch calibration. Choose manual
              corners, standard-pitch keypoints, or relative movement below. AI event suggestions do
              not confirm goals or update the score.
            </p>
          </div>
          <Upload className="size-6 text-brand-700" aria-hidden="true" />
        </div>
        <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="min-w-0 flex-1">
            <span className="mb-1.5 block text-sm font-semibold text-slate-700">
              Video file
            </span>
            <input
              accept=".mp4,.m4v,.mov,.webm,video/mp4,video/quicktime,video/webm"
              className="block min-h-11 w-full min-w-0 rounded-xl border border-border bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:font-semibold file:text-brand-800"
              disabled={uploading || hasActiveJob || Boolean(busyJobId) || loading}
              onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
              ref={inputRef}
              type="file"
            />
          </label>
          <Button
            disabled={!file || !calibration || hasActiveJob || Boolean(busyJobId) || loading}
            loading={uploading}
            onClick={uploadVideo}
          >
            {uploading ? "Uploading video" : "Upload and analyze"}
          </Button>
        </div>
        {file ? (
          <>
            <p className="mt-3 break-all text-sm text-slate-500">
              {file.name} · {(file.size / (1024 * 1024)).toFixed(1)} MB
            </p>
            <PitchCalibrationEditor key={`${file.name}:${file.size}:${file.lastModified}`} file={file} disabled={uploading || hasActiveJob || Boolean(busyJobId)} onChange={setCalibration} />
          </>
        ) : null}
        {uploading ? (
          <div className="mt-4" aria-live="polite">
            <p className="text-sm font-semibold text-slate-700">
              {uploadProgress < 100
                ? `Uploading video: ${uploadProgress}%`
                : "Upload sent. Validating video and creating the analysis job…"}
            </p>
            <progress className="mt-2 h-2 w-full accent-brand-700" max={100} value={uploadProgress} />
            {uploadProgress < 100 ? (
              <Button className="mt-2" onClick={() => uploadController.current?.abort()} size="sm" variant="ghost">
                Cancel upload
              </Button>
            ) : null}
          </div>
        ) : hasActiveJob ? (
          <p className="mt-4 rounded-xl bg-brand-50 p-3 text-sm text-brand-800" role="status">
            This match is being analyzed. Progress below updates automatically; another video can be uploaded when it finishes.
          </p>
        ) : null}
      </Card>

      {error ? <ErrorState compact message={error} title="Processing action failed" /> : null}
      {refreshError ? <ErrorState compact message={refreshError} onRetry={() => void refreshJobs()} title="Status unavailable" /> : null}

      <Card>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              Processing history
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Progress reflects backend worker reports and is never timer-generated.
            </p>
          </div>
          <Button
            aria-label="Refresh processing jobs"
            loading={refreshing}
            onClick={() => void refreshJobs()}
            size="sm"
            variant="ghost"
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            Refresh
          </Button>
        </div>

        {loading ? (
          <div className="mt-5">
            <LoadingSkeleton lines={5} label="Loading processing jobs" />
          </div>
        ) : jobs.length === 0 ? (
          <EmptyState
            compact
            description="Upload a real match video to create the first processing job."
            icon={Video}
            title="No processing jobs"
          />
        ) : (
          <div className="mt-5 space-y-4">
            {jobs.map((job) => (
              <ProcessingJobCard
                busy={busyJobId === job.id}
                retryDisabled={hasActiveJob || uploading || Boolean(busyJobId)}
                job={job}
                key={job.id}
                matchId={matchId}
                onRetry={() => retryJob(job.id)}
              />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function ProcessingJobCard({
  busy,
  job,
  matchId,
  onRetry,
  retryDisabled,
}: {
  busy: boolean;
  job: ProcessingJob;
  matchId: string;
  onRetry: () => void;
  retryDisabled: boolean;
}) {
  const status = PROCESSING_STATUS[job.status];
  const timestamp = job.failed_at ?? job.completed_at ?? job.started_at ?? job.created_at;

  return (
    <article className="rounded-xl border border-border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge dot variant={status.variant}>
              {status.label}
            </Badge>
            {job.retry_of_id ? <Badge>Retry</Badge> : null}
          </div>
          <h3 className="mt-3 font-semibold text-slate-950">
            {PROCESSING_STAGE_LABELS[job.stage]}
          </h3>
          <p className="mt-1 inline-flex items-center gap-1.5 text-xs text-slate-500">
            <Clock3 className="size-3.5" aria-hidden="true" />
            {formatJobTime(timestamp)}
          </p>
        </div>
        {job.status === "completed" ? (
          <CheckCircle2 className="size-6 text-success-700" aria-label="Completed" />
        ) : job.status === "failed" ? (
          <AlertTriangle className="size-6 text-danger-700" aria-label="Failed" />
        ) : null}
      </div>

      {job.status === "queued" || job.status === "processing" ? (
        <div className="mt-4">
          <div className="flex justify-between gap-3 text-xs font-semibold text-slate-500">
            <span>{job.progress === null ? "Progress unavailable" : "Progress"}</span>
            <span>{job.progress === null ? "—" : `${job.progress}%`}</span>
          </div>
          <div
            aria-label={
              job.progress === null
                ? "Processing progress is indeterminate"
                : `Processing progress ${job.progress} percent`
            }
            className="mt-2 h-2 overflow-hidden rounded-full bg-subtle"
            role="progressbar"
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={job.progress ?? undefined}
          >
            <div
              className={
                job.progress === null
                  ? "h-full w-full animate-pulse bg-brand-200"
                  : "h-full rounded-full bg-brand-600 transition-[width]"
              }
              style={
                job.progress === null ? undefined : { width: `${job.progress}%` }
              }
            />
          </div>
        </div>
      ) : null}

      {job.status === "failed" ? (
        <div className="mt-4 rounded-xl bg-danger-50 p-4">
          <p className="text-sm font-semibold text-danger-800">
            {job.error_message ?? "Video processing could not be completed."}
          </p>
          {job.error_code ? (
            <p className="mt-1 text-xs text-danger-700">Code: {job.error_code}</p>
          ) : null}
          <Button
            className="mt-3"
            disabled={retryDisabled}
            loading={busy}
            onClick={onRetry}
            size="sm"
            variant="secondary"
          >
            Retry processing
          </Button>
        </div>
      ) : null}

      {job.status === "completed" ? (
        <Link
          className="mt-4 inline-flex min-h-11 items-center text-sm font-semibold text-brand-700 hover:text-brand-900"
          href={`/matches/${matchId}?tab=players`}
        >
          View player analytics
        </Link>
      ) : null}
    </article>
  );
}

function uploadErrorMessage(caught: unknown): string {
  if (!(caught instanceof ApiError)) {
    return "The video could not be uploaded. Check your connection and try again.";
  }
  switch (caught.problem?.errorCode) {
    case "VIDEO_TOO_LARGE":
      return "The selected video exceeds the configured upload limit.";
    case "INVALID_VIDEO":
      return "Select a valid MP4, MOV, or WebM video.";
    case "ORGANIZER_ACCESS_DENIED":
      return "Organizer access has expired for this match.";
    case "UPLOAD_FAILED":
      return "The video could not be stored. Try again in a moment.";
    case "INVALID_CALIBRATION":
      return caught.problem?.detail ?? "Check the pitch dimensions and corner selection.";
    default:
      if (caught.status === 413) return "The selected video exceeds the server upload limit.";
      if (caught.status === 401 || caught.status === 403) return "Organizer access is required. Sign in as the match owner or use the browser where it was created.";
      return "The video could not be uploaded.";
  }
}

function formatJobTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
