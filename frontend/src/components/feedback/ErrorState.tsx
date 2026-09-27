import { CircleAlert } from "lucide-react";

import { Button } from "@/components/ui/Button";

interface ErrorStateProps {
  title: string;
  message: string;
  onRetry?: () => void;
  compact?: boolean;
}

export function ErrorState({
  compact = false,
  title,
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      className={`rounded-xl border border-danger-100 bg-danger-50 ${
        compact ? "p-4" : "p-5 sm:p-6"
      }`}
      role="alert"
    >
      <div className="flex min-w-0 items-start gap-3">
        <CircleAlert
          className="mt-0.5 size-5 shrink-0 text-danger-700"
          aria-hidden="true"
        />
        <div className="min-w-0">
          <h2 className="font-semibold text-danger-800">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-danger-700">{message}</p>
        </div>
      </div>
      {onRetry ? (
        <Button
          className="mt-4"
          onClick={onRetry}
          size="sm"
          variant="secondary"
        >
          Try again
        </Button>
      ) : null}
    </div>
  );
}
