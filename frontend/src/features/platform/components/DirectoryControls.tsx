"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

interface DebouncedSearchProps {
  label: string;
  placeholder: string;
}

export function DebouncedSearch({
  label,
  placeholder,
}: DebouncedSearchProps) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const timer = useRef<number | null>(null);
  const currentQuery = searchParams.get("q") ?? "";

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    },
    [],
  );

  return (
    <label className="relative block min-w-0 flex-1">
      <span className="sr-only">{label}</span>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400"
        aria-hidden="true"
      />
      <input
        className="h-11 w-full rounded-xl border border-border bg-white pl-10 pr-3 text-sm text-slate-950 placeholder:text-slate-400 focus:border-brand-600 focus:outline-2 focus:outline-offset-1 focus:outline-brand-600"
        defaultValue={currentQuery}
        key={currentQuery}
        onChange={(event) => {
          const value = event.target.value;
          if (timer.current !== null) window.clearTimeout(timer.current);
          timer.current = window.setTimeout(() => {
            const next = new URLSearchParams(searchParams.toString());
            if (value.trim()) next.set("q", value.trim());
            else next.delete("q");
            next.delete("page");
            router.push(`${pathname}?${next.toString()}`);
          }, 350);
        }}
        placeholder={placeholder}
        type="search"
      />
    </label>
  );
}

export function PlatformPagination({
  page,
  totalPages,
}: {
  page: number;
  totalPages: number;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  if (totalPages <= 1) return null;

  function href(nextPage: number) {
    const next = new URLSearchParams(searchParams.toString());
    if (nextPage === 1) next.delete("page");
    else next.set("page", String(nextPage));
    return `${pathname}?${next.toString()}`;
  }

  return (
    <nav
      aria-label="Pagination"
      className="mt-6 flex items-center justify-between gap-4"
    >
      {page > 1 ? (
        <Link className={paginationClass} href={href(page - 1)}>
          Previous
        </Link>
      ) : (
        <span className={`${paginationClass} opacity-40`}>Previous</span>
      )}
      <span className="text-sm font-semibold text-slate-500">
        Page {page} of {totalPages}
      </span>
      {page < totalPages ? (
        <Link className={paginationClass} href={href(page + 1)}>
          Next
        </Link>
      ) : (
        <span className={`${paginationClass} opacity-40`}>Next</span>
      )}
    </nav>
  );
}

export function updateQueryHref(
  pathname: string,
  searchParams: URLSearchParams,
  updates: Record<string, string>,
) {
  const next = new URLSearchParams(searchParams.toString());
  Object.entries(updates).forEach(([key, value]) => {
    if (value) next.set(key, value);
    else next.delete(key);
  });
  next.delete("page");
  return `${pathname}?${next.toString()}`;
}

const paginationClass =
  "inline-flex min-h-11 items-center rounded-xl border border-border bg-white px-4 text-sm font-semibold text-slate-700 hover:border-brand-300 hover:text-brand-800 focus-visible:outline-2 focus-visible:outline-brand-700";
