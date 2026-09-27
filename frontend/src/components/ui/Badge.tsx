import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type BadgeVariant = "neutral" | "brand" | "success" | "warning" | "danger" | "info";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  dot?: boolean;
}

const variantClasses: Record<BadgeVariant, string> = {
  neutral: "bg-subtle text-slate-700",
  brand: "bg-brand-100 text-brand-800",
  success: "bg-success-100 text-success-800",
  warning: "bg-warning-100 text-warning-800",
  danger: "bg-danger-100 text-danger-800",
  info: "bg-info-100 text-info-800",
};

export function Badge({
  children,
  className,
  dot = false,
  variant = "neutral",
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold",
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {dot ? (
        <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />
      ) : null}
      <span className="truncate">{children}</span>
    </span>
  );
}
