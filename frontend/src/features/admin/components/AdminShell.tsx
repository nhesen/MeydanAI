"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { PageContainer } from "@/components/layout/PageContainer";
import { cn } from "@/lib/cn";

const ADMIN_LINKS = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/matches", label: "Matches" },
  { href: "/admin/players", label: "Players" },
  { href: "/admin/teams", label: "Teams" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/highlights", label: "Highlights" },
  { href: "/admin/users", label: "Users" },
];

export function AdminShell({
  children,
  title,
  description,
}: {
  children: ReactNode;
  title: string;
  description: string;
}) {
  const pathname = usePathname();

  return (
    <PageContainer className="max-w-7xl">
      <header>
        <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-brand-700">
          Administration
        </p>
        <h1 className="type-page-title text-slate-950">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{description}</p>
      </header>
      <nav
        aria-label="Admin sections"
        className="mt-6 flex gap-2 overflow-x-auto pb-1"
      >
        {ADMIN_LINKS.map((item) => {
          const active =
            item.href === "/admin"
              ? pathname === "/admin"
              : pathname.startsWith(item.href);
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={cn(
                "inline-flex min-h-11 shrink-0 items-center rounded-xl px-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-brand-700",
                active
                  ? "bg-brand-50 text-brand-800"
                  : "text-slate-600 hover:bg-subtle",
              )}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-6">{children}</div>
    </PageContainer>
  );
}
