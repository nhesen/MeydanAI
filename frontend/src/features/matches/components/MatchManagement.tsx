"use client";

import { Check, Copy, LockKeyhole } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { useCallback, useEffect, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { QR_COLORS } from "@/config/brand";
import { ApiError, api } from "@/services/api-client";
import type { JerseyAssignment, MatchSummary } from "@/types/api";

interface MatchManagementProps {
  matchId: string;
}

interface EditState {
  teamId: string;
  jersey: string;
  override: boolean;
  reason: string;
}

export function MatchManagement({ matchId }: MatchManagementProps) {
  const [organizerToken, setOrganizerToken] = useState<string | null>(null);
  const [joinUrl, setJoinUrl] = useState("");
  const [match, setMatch] = useState<MatchSummary | null>(null);
  const [assignments, setAssignments] = useState<JerseyAssignment[]>([]);
  const [edits, setEdits] = useState<Record<string, EditState>>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async (token: string, signal?: AbortSignal) => {
    const [matchResponse, assignmentResponse] = await Promise.all([
      api.getMatch(matchId, token, signal),
      api.getAssignments(matchId, token, signal),
    ]);
    setMatch(matchResponse.data);
    setAssignments(assignmentResponse.data);
    setEdits(
      Object.fromEntries(
        assignmentResponse.data
          .filter((item) => !item.ended_at)
          .map((item) => [
            item.id,
            {
              teamId: item.team.id,
              jersey: String(item.jersey_number),
              override: false,
              reason: "",
            },
          ]),
      ),
    );
  }, [matchId]);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;

    async function initialize() {
      await Promise.resolve();
      if (cancelled) return;
      const token = sessionStorage.getItem(`meydanai:organizer:${matchId}`);
      setJoinUrl(sessionStorage.getItem(`meydanai:join:${matchId}`) ?? "");
      if (!token) {
        setLoading(false);
        return;
      }
      setOrganizerToken(token);
      try {
        await load(token, controller.signal);
      } catch {
        if (!controller.signal.aborted) {
          setError("Match management data could not be loaded.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void initialize();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [load, matchId]);

  async function applyChange(assignment: JerseyAssignment) {
    if (!organizerToken) return;
    const edit = edits[assignment.id];
    if (!edit) return;
    setBusyId(assignment.id);
    setError(null);
    try {
      const common = {
        override_conflict: edit.override,
        override_reason: edit.override ? edit.reason : undefined,
        override_actor: edit.override ? "Organizer" : undefined,
      };
      if (edit.teamId === assignment.team.id) {
        await api.changeJersey(matchId, assignment.id, organizerToken, {
          jersey_number: Number(edit.jersey),
          ...common,
        });
      } else {
        await api.correctAssignment(matchId, assignment.id, organizerToken, {
          team_id: edit.teamId,
          jersey_number: Number(edit.jersey),
          ...common,
        });
      }
      await load(organizerToken);
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError && caught.problem?.errorCode === "JERSEY_IN_USE"
          ? "That jersey is already in use. Use an explicit override only when necessary."
          : "The assignment could not be updated.",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function closeAssignment(assignmentId: string) {
    if (!organizerToken) return;
    setBusyId(assignmentId);
    try {
      await api.correctAssignment(matchId, assignmentId, organizerToken, {
        close_only: true,
      });
      await load(organizerToken);
    } catch {
      setError("The assignment could not be closed.");
    } finally {
      setBusyId(null);
    }
  }

  function updateEdit(assignmentId: string, update: Partial<EditState>) {
    setEdits((current) => ({
      ...current,
      [assignmentId]: { ...current[assignmentId], ...update },
    }));
  }

  async function copyJoinLink() {
    await navigator.clipboard.writeText(joinUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  if (loading) {
    return <LoadingSkeleton lines={6} label="Loading match management" />;
  }

  if (!organizerToken) {
    return (
      <Card>
        <div className="flex items-start gap-3">
          <LockKeyhole className="mt-0.5 size-5 text-warning-700" aria-hidden="true" />
          <div>
            <h2 className="font-semibold text-slate-950">Organizer access required</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              Open this page in the same browser tab where the match was created.
              Full account-based recovery will arrive with authentication.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      {error ? <ErrorState compact message={error} title="Action failed" /> : null}
      {joinUrl ? (
        <Card className="grid items-center gap-5 sm:grid-cols-[1fr_auto]">
          <div className="min-w-0">
            <Badge variant="brand">Player entry</Badge>
            <h2 className="mt-3 text-lg font-semibold text-slate-950">Join link</h2>
            <p className="mt-1 break-all text-sm text-slate-600">{joinUrl}</p>
            <Button className="mt-4" onClick={copyJoinLink} size="sm" variant="secondary">
              {copied ? (
                <Check className="size-4" aria-hidden="true" />
              ) : (
                <Copy className="size-4" aria-hidden="true" />
              )}
              {copied ? "Copied" : "Copy link"}
            </Button>
          </div>
          <div className="justify-self-center rounded-xl border border-border bg-white p-2">
            <QRCodeSVG
              aria-label="Match join QR code"
              bgColor={QR_COLORS.background}
              fgColor={QR_COLORS.foreground}
              level="M"
              marginSize={1}
              size={132}
              value={joinUrl}
            />
          </div>
        </Card>
      ) : null}

      <Card>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Assignments</h2>
            <p className="mt-1 text-sm text-slate-500">
              {match?.teams.map((team) => team.name).join(" vs ")}
            </p>
          </div>
          <Badge>{assignments.length} records</Badge>
        </div>

        {assignments.length === 0 ? (
          <p className="mt-6 rounded-xl bg-subtle p-4 text-sm text-slate-600">
            Player assignments will appear as participants join.
          </p>
        ) : (
          <div className="mt-5 space-y-4">
            {assignments.map((assignment) => {
              const edit = edits[assignment.id];
              const active = !assignment.ended_at;
              return (
                <div className="rounded-xl border border-border p-4" key={assignment.id}>
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-slate-950">
                        {assignment.player.display_name}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">
                        {assignment.team.name} · #{assignment.jersey_number}
                      </p>
                    </div>
                    <Badge variant={active ? "success" : "neutral"}>
                      {active ? "Active" : "Closed"}
                    </Badge>
                  </div>
                  {active && edit ? (
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <select
                        aria-label={`Team for ${assignment.player.display_name}`}
                        className="h-11 rounded-xl border border-border bg-surface px-3 text-sm"
                        onChange={(event) =>
                          updateEdit(assignment.id, { teamId: event.target.value })
                        }
                        value={edit.teamId}
                      >
                        {match?.teams.map((team) => (
                          <option key={team.id} value={team.id}>
                            {team.name}
                          </option>
                        ))}
                      </select>
                      <Input
                        aria-label={`Jersey for ${assignment.player.display_name}`}
                        max={99}
                        min={0}
                        onChange={(event) =>
                          updateEdit(assignment.id, { jersey: event.target.value })
                        }
                        type="number"
                        value={edit.jersey}
                      />
                      <label className="flex min-h-11 items-center gap-2 text-sm text-slate-700">
                        <input
                          checked={edit.override}
                          onChange={(event) =>
                            updateEdit(assignment.id, {
                              override: event.target.checked,
                            })
                          }
                          type="checkbox"
                        />
                        Explicit conflict override
                      </label>
                      {edit.override ? (
                        <Input
                          aria-label="Override reason"
                          onChange={(event) =>
                            updateEdit(assignment.id, { reason: event.target.value })
                          }
                          placeholder="Required audit reason"
                          value={edit.reason}
                        />
                      ) : null}
                      <div className="flex gap-2 sm:col-span-2">
                        <Button
                          loading={busyId === assignment.id}
                          onClick={() => applyChange(assignment)}
                          size="sm"
                        >
                          Apply change
                        </Button>
                        <Button
                          disabled={busyId === assignment.id}
                          onClick={() => closeAssignment(assignment.id)}
                          size="sm"
                          variant="ghost"
                        >
                          Close assignment
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
