"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.error(error);
    }
  }, [error]);

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl items-center px-4 py-12">
      <ErrorState
        title="Something went wrong"
        message="The page could not be displayed. Please try again."
        onRetry={reset}
      />
    </main>
  );
}
