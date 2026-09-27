import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function PageContainer({
  children,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 xl:px-8",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
