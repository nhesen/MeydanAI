import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type CardPadding = "none" | "sm" | "md" | "lg";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: CardPadding;
}

const paddingClasses: Record<CardPadding, string> = {
  none: "",
  sm: "p-4",
  md: "p-5 sm:p-6",
  lg: "p-6 sm:p-8",
};

export function Card({
  children,
  className,
  padding = "md",
  ...props
}: CardProps) {
  return (
    <div
      className={cn(
        "min-w-0 rounded-2xl border border-border bg-surface shadow-card",
        paddingClasses[padding],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
