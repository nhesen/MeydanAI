import { SystemHealthCard } from "@/features/system-health/components/SystemHealthCard";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-4 py-12 sm:px-6 lg:px-8">
      <div className="grid items-center gap-10 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-700">
            MeydanAI
          </p>
          <h1 className="mt-4 max-w-2xl text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl">
            Football analytics, built on a reliable foundation.
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-slate-600 sm:text-lg">
            The application foundation is ready for match, player, team and
            movement analytics modules.
          </p>
        </div>
        <SystemHealthCard />
      </div>
    </main>
  );
}
