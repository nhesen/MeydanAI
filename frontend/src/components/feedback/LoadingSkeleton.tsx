import { cn } from "@/lib/cn";

interface LoadingSkeletonProps {
  lines?: number;
  label?: string;
  className?: string;
}

export function LoadingSkeleton({
  className,
  lines = 3,
  label = "Content is loading",
}: LoadingSkeletonProps) {
  return (
    <div
      className={cn("space-y-3", className)}
      aria-busy="true"
      aria-label={label}
      role="status"
    >
      {Array.from({ length: lines }, (_, index) => (
        <div
          className="h-4 animate-pulse rounded-md bg-subtle last:w-2/3"
          key={index}
        />
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}
