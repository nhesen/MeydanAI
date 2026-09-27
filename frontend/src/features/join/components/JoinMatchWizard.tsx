"use client";

import { CheckCircle2, ChevronLeft, Shirt, UserRound, UsersRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { ApiError, api } from "@/services/api-client";
import type { JerseyAssignment, JoinContext } from "@/types/api";
import { cn } from "@/lib/cn";

interface JoinMatchWizardProps {
  token: string;
}

const stepLabels = ["Match", "Team", "Player", "Jersey", "Review"];

export function JoinMatchWizard({ token }: JoinMatchWizardProps) {
  const [context, setContext] = useState<JoinContext | null>(null);
  const [step, setStep] = useState(0);
  const [teamId, setTeamId] = useState("");
  const [playerMode, setPlayerMode] = useState<"existing" | "new">("new");
  const [playerId, setPlayerId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [jersey, setJersey] = useState("");
  const [assignment, setAssignment] = useState<JerseyAssignment | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ title: string; message: string } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .getJoinContext(token, controller.signal)
      .then((response) => setContext(response.data))
      .catch((caught: unknown) => {
        const code = caught instanceof ApiError ? caught.problem?.errorCode : undefined;
        const states: Record<string, { title: string; message: string }> = {
          JOIN_TOKEN_EXPIRED: {
            title: "Join link expired",
            message: "Ask the organizer for a new match link.",
          },
          JOIN_TOKEN_REVOKED: {
            title: "Join link revoked",
            message: "This link is no longer active. Ask the organizer for a new one.",
          },
          MATCH_CLOSED: {
            title: "Match is closed",
            message: "Player entry is no longer available for this match.",
          },
        };
        setError(
          (code ? states[code] : undefined) ?? {
            title: "Match not found",
            message: "Check the QR code or ask the organizer for a valid link.",
          },
        );
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [token]);

  const selectedTeam = context?.match.teams.find((team) => team.id === teamId);
  const selectedPlayer = useMemo(
    () => context?.players.find((player) => player.id === playerId),
    [context?.players, playerId],
  );

  function canContinue(): boolean {
    if (step === 1) return Boolean(teamId);
    if (step === 2) {
      return playerMode === "existing"
        ? Boolean(playerId)
        : displayName.trim().length >= 2;
    }
    if (step === 3) {
      const value = Number(jersey);
      return jersey !== "" && Number.isInteger(value) && value >= 0 && value <= 99;
    }
    return true;
  }

  async function confirm() {
    setSubmitting(true);
    setError(null);
    try {
      const response = await api.createAssignment(token, {
        team_id: teamId,
        jersey_number: Number(jersey),
        ...(playerMode === "existing"
          ? { player_id: playerId }
          : { display_name: displayName.trim() }),
      });
      setAssignment(response.data);
      setStep(5);
    } catch (caught: unknown) {
      const jerseyConflict =
        caught instanceof ApiError &&
        caught.problem?.errorCode === "JERSEY_IN_USE";
      setError({
        title: jerseyConflict ? "Jersey already in use" : "Could not join match",
        message: jerseyConflict
          ? "Choose another jersey number and try again."
          : "Please review your choices and try again.",
      });
      if (jerseyConflict) setStep(3);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-lg px-4 py-8">
        <Card>
          <LoadingSkeleton lines={6} label="Opening match join flow" />
        </Card>
      </div>
    );
  }

  if (!context) {
    return (
      <div className="mx-auto w-full max-w-lg px-4 py-8">
        <ErrorState
          message={error?.message ?? "This match could not be opened."}
          title={error?.title ?? "Match unavailable"}
        />
      </div>
    );
  }

  if (step === 5 && assignment) {
    return (
      <div className="mx-auto w-full max-w-lg px-4 py-8 sm:py-12">
        <Card className="text-center" padding="lg">
          <div className="mx-auto grid size-14 place-items-center rounded-full bg-success-100 text-success-700">
            <CheckCircle2 className="size-7" aria-hidden="true" />
          </div>
          <Badge className="mt-5" variant="success">
            Joined successfully
          </Badge>
          <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-950">
            You&apos;re in!
          </h1>
          <p className="mt-2 text-slate-600">{assignment.player.display_name}</p>
          <div className="mx-auto mt-6 flex max-w-xs items-center justify-center gap-5 rounded-2xl bg-subtle p-5">
            <div>
              <p className="type-stat-label">TEAM</p>
              <p className="mt-1 font-semibold text-slate-950">{assignment.team.name}</p>
            </div>
            <div className="h-10 w-px bg-border" aria-hidden="true" />
            <div>
              <p className="type-stat-label">JERSEY</p>
              <p className="type-stat-value mt-1 text-brand-800">
                #{assignment.jersey_number}
              </p>
            </div>
          </div>
          <Link
            className="mt-7 inline-flex h-11 items-center justify-center rounded-xl border border-border bg-surface px-4 text-sm font-semibold text-slate-800 hover:bg-subtle"
            href="/"
          >
            Back to MeydanAI
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-lg px-4 py-6 sm:py-10">
      <div className="mb-5 flex items-center justify-between gap-2" aria-label="Join progress">
        {stepLabels.map((label, index) => (
          <div className="min-w-0 flex-1" key={label}>
            <div
              className={cn(
                "h-1.5 rounded-full",
                index <= step ? "bg-brand-700" : "bg-border",
              )}
            />
            <span className="sr-only">
              {label}: {index <= step ? "complete or current" : "upcoming"}
            </span>
          </div>
        ))}
      </div>

      {error ? (
        <ErrorState compact message={error.message} title={error.title} />
      ) : null}

      <Card className={error ? "mt-4" : undefined} padding="lg">
        {step === 0 ? (
          <div>
            <Badge variant="brand">{context.match.status}</Badge>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-950">
              Join match
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {context.match.title ?? "Small-sided football match"}
            </p>
            <dl className="mt-6 space-y-4 rounded-2xl bg-subtle p-5 text-sm">
              <div>
                <dt className="type-stat-label">TEAMS</dt>
                <dd className="mt-1 font-semibold text-slate-950">
                  {context.match.teams.map((team) => team.name).join(" vs ")}
                </dd>
              </div>
              <div>
                <dt className="type-stat-label">VENUE</dt>
                <dd className="mt-1 text-slate-700">{context.match.venue_name}</dd>
              </div>
              <div>
                <dt className="type-stat-label">START</dt>
                <dd className="mt-1 text-slate-700">
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  }).format(new Date(context.match.starts_at))}
                </dd>
              </div>
            </dl>
          </div>
        ) : null}

        {step === 1 ? (
          <div>
            <UsersRound className="size-6 text-brand-700" aria-hidden="true" />
            <h1 className="mt-3 text-2xl font-bold text-slate-950">Select your team</h1>
            <div className="mt-5 grid gap-3">
              {context.match.teams.map((team) => (
                <button
                  className={cn(
                    "min-h-16 rounded-2xl border p-4 text-left font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700",
                    teamId === team.id
                      ? "border-brand-600 bg-brand-50 text-brand-900"
                      : "border-border bg-surface text-slate-800 hover:bg-subtle",
                  )}
                  key={team.id}
                  onClick={() => setTeamId(team.id)}
                  type="button"
                >
                  {team.name}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div>
            <UserRound className="size-6 text-brand-700" aria-hidden="true" />
            <h1 className="mt-3 text-2xl font-bold text-slate-950">Who are you?</h1>
            <div className="mt-5 flex rounded-xl bg-subtle p-1">
              <button
                className={cn(
                  "h-10 flex-1 rounded-lg text-sm font-semibold",
                  playerMode === "new" ? "bg-surface text-slate-950 shadow-sm" : "text-slate-600",
                )}
                onClick={() => setPlayerMode("new")}
                type="button"
              >
                New player
              </button>
              <button
                className={cn(
                  "h-10 flex-1 rounded-lg text-sm font-semibold",
                  playerMode === "existing"
                    ? "bg-surface text-slate-950 shadow-sm"
                    : "text-slate-600",
                )}
                disabled={context.players.length === 0}
                onClick={() => setPlayerMode("existing")}
                type="button"
              >
                Existing
              </button>
            </div>
            {playerMode === "new" ? (
              <Input
                className="mt-4"
                maxLength={100}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Your display name"
                value={displayName}
              />
            ) : (
              <div className="mt-4 max-h-64 space-y-2 overflow-y-auto">
                {context.players.map((player) => (
                  <button
                    className={cn(
                      "min-h-12 w-full rounded-xl border px-4 text-left text-sm font-semibold",
                      playerId === player.id
                        ? "border-brand-600 bg-brand-50"
                        : "border-border",
                    )}
                    key={player.id}
                    onClick={() => setPlayerId(player.id)}
                    type="button"
                  >
                    {player.display_name}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : null}

        {step === 3 ? (
          <div>
            <Shirt className="size-6 text-brand-700" aria-hidden="true" />
            <h1 className="mt-3 text-2xl font-bold text-slate-950">Choose jersey</h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Enter the jersey or bib number you are wearing for this match.
            </p>
            <Input
              className="mt-5 h-16 text-center text-2xl font-bold"
              inputMode="numeric"
              max={99}
              min={0}
              onChange={(event) => setJersey(event.target.value)}
              placeholder="7"
              type="number"
              value={jersey}
            />
          </div>
        ) : null}

        {step === 4 ? (
          <div>
            <h1 className="text-2xl font-bold text-slate-950">Review entry</h1>
            <dl className="mt-5 divide-y divide-border rounded-2xl border border-border px-4">
              <ReviewRow label="Match" value={context.match.title ?? context.match.venue_name} />
              <ReviewRow label="Team" value={selectedTeam?.name ?? ""} />
              <ReviewRow
                label="Player"
                value={
                  playerMode === "existing"
                    ? selectedPlayer?.display_name ?? ""
                    : displayName.trim()
                }
              />
              <ReviewRow label="Jersey" value={`#${jersey}`} />
            </dl>
          </div>
        ) : null}

        <div className="mt-7 flex items-center justify-between gap-3 border-t border-border pt-5">
          {step > 0 ? (
            <Button onClick={() => setStep((current) => current - 1)} variant="ghost">
              <ChevronLeft className="size-4" aria-hidden="true" />
              Back
            </Button>
          ) : (
            <span />
          )}
          {step < 4 ? (
            <Button disabled={!canContinue()} onClick={() => setStep((current) => current + 1)}>
              Continue
            </Button>
          ) : (
            <Button loading={submitting} onClick={confirm}>
              Confirm and join
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-4 py-4">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="truncate text-right text-sm font-semibold text-slate-950">{value}</dd>
    </div>
  );
}
