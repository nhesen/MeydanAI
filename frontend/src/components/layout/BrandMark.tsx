import Link from "next/link";

import { cn } from "@/lib/cn";

interface BrandMarkProps {
  compact?: boolean;
  className?: string;
}

export function BrandMark({ className, compact = false }: BrandMarkProps) {
  return (
    <Link
      className={cn(
        "inline-flex min-w-0 items-center gap-2.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-700",
        className,
      )}
      href="/"
      aria-label="MeydanAI home"
    >
      <span
        className="grid size-9 shrink-0 place-items-center rounded-xl bg-brand-700 text-sm font-bold tracking-tight text-white"
        aria-hidden="true"
      >
        M
      </span>
      {!compact ? (
        <span className="truncate text-lg font-bold tracking-[-0.03em] text-slate-950">
          Meydan<span className="text-brand-700">AI</span>
        </span>
      ) : null}
    </Link>
  );
}
