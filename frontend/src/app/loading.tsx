import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";

export default function Loading() {
  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <LoadingSkeleton lines={5} label="Loading page" />
      </div>
    </main>
  );
}
