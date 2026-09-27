interface LoadingSkeletonProps {
  lines?: number;
  label?: string;
}

export function LoadingSkeleton({
  lines = 3,
  label = "Content is loading",
}: LoadingSkeletonProps) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label={label} role="status">
      {Array.from({ length: lines }, (_, index) => (
        <div
          className="h-4 animate-pulse rounded-md bg-slate-200 last:w-2/3"
          key={index}
        />
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}
