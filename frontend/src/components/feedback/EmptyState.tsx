import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
  action?: ReactNode;
  compact?: boolean;
  className?: string;
}

export function EmptyState({
  action,
  className,
  compact = false,
  description,
  icon: Icon,
  title,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col items-center justify-center text-center",
        compact ? "px-4 py-8" : "px-5 py-12 sm:px-8 sm:py-16",
        className,
      )}
    >
      {Icon ? (
        <div className="mb-4 flex size-11 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
          <Icon className="size-5" strokeWidth={1.8} aria-hidden="true" />
        </div>
      ) : null}
      <h2 className="type-section-title max-w-sm text-slate-950">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-600">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
