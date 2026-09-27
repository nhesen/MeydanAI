"use client";

import { Check, Copy, ExternalLink } from "lucide-react";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { type FormEvent, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { QR_COLORS } from "@/config/brand";
import { getAppBaseUrl } from "@/lib/env";
import { ApiError, api } from "@/services/api-client";
import type { MatchCreated } from "@/types/api";

interface FormState {
  title: string;
  venue: string;
  startsAt: string;
  endsAt: string;
  teamA: string;
  teamB: string;
}

const initialForm: FormState = {
  title: "",
  venue: "",
  startsAt: "",
  endsAt: "",
  teamA: "",
  teamB: "",
};

export function MatchCreateForm() {
  const [form, setForm] = useState(initialForm);
  const [created, setCreated] = useState<MatchCreated | null>(null);
  const [joinUrl, setJoinUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update(field: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (form.teamA.trim().toLowerCase() === form.teamB.trim().toLowerCase()) {
      setError("Team A and Team B must be different.");
      return;
    }
    setLoading(true);
    try {
      const response = await api.createMatch({
        title: form.title.trim() || null,
        venue_name: form.venue.trim(),
        starts_at: new Date(form.startsAt).toISOString(),
        expected_ends_at: form.endsAt
          ? new Date(form.endsAt).toISOString()
          : null,
        team_a_name: form.teamA.trim(),
        team_b_name: form.teamB.trim(),
      });
      const result = response.data;
      const url = `${getAppBaseUrl()}/join/${result.join_token}`;
      sessionStorage.setItem(
        `meydanai:organizer:${result.match.id}`,
        result.organizer_token,
      );
      sessionStorage.setItem(`meydanai:join:${result.match.id}`, url);
      setCreated(result);
      setJoinUrl(url);
    } catch (caught: unknown) {
      setError(
        caught instanceof ApiError && caught.status === 422
          ? "Check the match details and try again."
          : "The match could not be created. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function copyLink() {
    await navigator.clipboard.writeText(joinUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  }

  if (created) {
    return (
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Card>
          <Badge dot variant="success">
            Match created
          </Badge>
          <h2 className="mt-4 text-2xl font-bold tracking-tight text-slate-950">
            Share the join link
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Players can scan the QR code or open the link to choose their team,
            player and jersey.
          </p>
          <div className="mt-5 break-all rounded-xl border border-border bg-subtle p-3 text-sm text-slate-700">
            {joinUrl}
          </div>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row">
            <Button onClick={copyLink} variant="secondary">
              {copied ? (
                <Check className="size-4" aria-hidden="true" />
              ) : (
                <Copy className="size-4" aria-hidden="true" />
              )}
              {copied ? "Copied" : "Copy link"}
            </Button>
            <Link
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-brand-700 px-4 text-sm font-semibold text-white transition hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700"
              href={`/matches/${created.match.id}/manage`}
            >
              Manage match
              <ExternalLink className="size-4" aria-hidden="true" />
            </Link>
          </div>
        </Card>
        <Card className="flex items-center justify-center">
          <div className="rounded-2xl border border-border bg-white p-4">
            <QRCodeSVG
              aria-label="Match join QR code"
              bgColor={QR_COLORS.background}
              fgColor={QR_COLORS.foreground}
              level="M"
              marginSize={1}
              size={220}
              value={joinUrl}
            />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <Card>
      {error ? (
        <ErrorState compact message={error} title="Could not create match" />
      ) : null}
      <form className={error ? "mt-5 space-y-5" : "space-y-5"} onSubmit={submit}>
        <div className="grid gap-5 sm:grid-cols-2">
          <Field htmlFor="match-title" label="Match title" hint="Optional">
            <Input
              id="match-title"
              maxLength={140}
              onChange={(event) => update("title", event.target.value)}
              placeholder="Sunday evening match"
              value={form.title}
            />
          </Field>
          <Field htmlFor="venue" label="Venue">
            <Input
              id="venue"
              maxLength={140}
              minLength={2}
              onChange={(event) => update("venue", event.target.value)}
              placeholder="Meydan Arena"
              required
              value={form.venue}
            />
          </Field>
          <Field htmlFor="starts-at" label="Start date and time">
            <Input
              id="starts-at"
              onChange={(event) => update("startsAt", event.target.value)}
              required
              type="datetime-local"
              value={form.startsAt}
            />
          </Field>
          <Field htmlFor="ends-at" label="Expected end" hint="Optional">
            <Input
              id="ends-at"
              onChange={(event) => update("endsAt", event.target.value)}
              type="datetime-local"
              value={form.endsAt}
            />
          </Field>
          <Field htmlFor="team-a" label="Team A">
            <Input
              id="team-a"
              maxLength={100}
              onChange={(event) => update("teamA", event.target.value)}
              placeholder="Home team"
              required
              value={form.teamA}
            />
          </Field>
          <Field htmlFor="team-b" label="Team B">
            <Input
              id="team-b"
              maxLength={100}
              onChange={(event) => update("teamB", event.target.value)}
              placeholder="Away team"
              required
              value={form.teamB}
            />
          </Field>
        </div>
        <div className="flex justify-end border-t border-border pt-5">
          <Button loading={loading} type="submit">
            Create match
          </Button>
        </div>
      </form>
    </Card>
  );
}
