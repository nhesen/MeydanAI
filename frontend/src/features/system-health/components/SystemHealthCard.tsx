"use client";

import { useEffect, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { api, ApiError } from "@/services/api-client";
import type { ServiceHealth } from "@/types/api";

type HealthState =
  | { status: "loading" }
  | { status: "success"; health: ServiceHealth }
  | { status: "error"; message: string };

export function SystemHealthCard() {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<HealthState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();

    api
      .getHealth(controller.signal)
      .then((response) => {
        setState({ status: "success", health: response.data });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        const message =
          error instanceof ApiError
            ? "The API returned an error. Please retry in a moment."
            : "The API is unavailable or the environment is not configured.";
        setState({ status: "error", message });
      });

    return () => controller.abort();
  }, [attempt]);

  return (
    <section
      className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
      aria-labelledby="api-status-heading"
    >
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700">
            Foundation
          </p>
          <h2
            className="mt-1 text-xl font-semibold text-slate-950"
            id="api-status-heading"
          >
            API status
          </h2>
        </div>
        {state.status === "success" ? (
          <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
            {state.health.status}
          </span>
        ) : null}
      </div>

      {state.status === "loading" ? (
        <LoadingSkeleton lines={2} label="Checking API status" />
      ) : null}

      {state.status === "error" ? (
        <ErrorState
          title="API connection failed"
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setAttempt((current) => current + 1);
          }}
        />
      ) : null}

      {state.status === "success" ? (
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-slate-500">Service</dt>
            <dd className="mt-1 font-medium text-slate-900">
              {state.health.service}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Connection</dt>
            <dd className="mt-1 font-medium text-emerald-700">Connected</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
