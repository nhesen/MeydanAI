"use client";

import { useEffect, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
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
    <Card>
      <SectionHeader
        title="Platform status"
        description="Live connection to the MeydanAI API."
        action={
          state.status === "success" ? (
            <Badge dot variant="success">
              Online
            </Badge>
          ) : null
        }
      />

      <div className="mt-5">
        {state.status === "loading" ? (
          <LoadingSkeleton lines={2} label="Checking API status" />
        ) : null}

        {state.status === "error" ? (
          <ErrorState
            compact
            title="API connection failed"
            message={state.message}
            onRetry={() => {
              setState({ status: "loading" });
              setAttempt((current) => current + 1);
            }}
          />
        ) : null}

        {state.status === "success" ? (
          <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <div className="min-w-0">
              <dt className="type-stat-label">SERVICE</dt>
              <dd className="mt-1 truncate font-semibold text-slate-900">
                {state.health.service}
              </dd>
            </div>
            <div>
              <dt className="type-stat-label">CONNECTION</dt>
              <dd className="mt-1 font-semibold text-success-700">Connected</dd>
            </div>
          </dl>
        ) : null}
      </div>
    </Card>
  );
}
