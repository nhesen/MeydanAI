"use client";

import { useState } from "react";

import { getApiBaseUrl } from "@/lib/env";

export function absoluteMediaUrl(src: string) {
  if (src.startsWith("http://") || src.startsWith("https://")) return src;
  return `${getApiBaseUrl()}${src}`;
}

export function ClipActions({ title, src }: { title: string; src: string }) {
  const [notice, setNotice] = useState<string | null>(null);
  const url = absoluteMediaUrl(src);

  async function share() {
    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title, url });
        return;
      } catch (caught: unknown) {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Link copied");
    } catch {
      setNotice(url);
    }
  }

  return (
    <div className="mt-3">
      <div className="flex flex-wrap gap-3 text-sm font-semibold">
        <button
          className="inline-flex min-h-11 items-center text-brand-800 hover:text-brand-950"
          onClick={() => void share()}
          type="button"
        >
          Share
        </button>
        <a
          className="inline-flex min-h-11 items-center text-slate-600 hover:text-slate-950"
          download
          href={url}
        >
          Download
        </a>
      </div>
      {notice ? (
        <p className="mt-1 break-all text-xs font-semibold text-slate-500">{notice}</p>
      ) : null}
    </div>
  );
}
