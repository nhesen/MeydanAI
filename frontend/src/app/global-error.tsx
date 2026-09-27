"use client";

import { useEffect } from "react";

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
    <html lang="en">
      <body className="min-h-full bg-[#f6f8f7] text-[#14221a]">
        <div className="mx-auto flex min-h-[70vh] w-full max-w-xl flex-col items-start justify-center px-4 py-12">
          <p className="text-sm font-semibold uppercase tracking-wider text-[#1c623a]">
            500
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">
            Something went wrong
          </h1>
          <p className="mt-3 leading-7 text-slate-600">
            The application could not recover from this error.
          </p>
          <button
            className="mt-6 rounded-lg bg-[#1c623a] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#194e32] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#1c623a]"
            onClick={reset}
            type="button"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
