import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-xl flex-col items-start justify-center px-4 py-12">
      <p className="text-sm font-semibold uppercase tracking-wider text-emerald-700">
        404
      </p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">
        Page not found
      </h1>
      <p className="mt-3 leading-7 text-slate-600">
        The page may have moved or no longer exists.
      </p>
      <Link
        className="mt-6 rounded-lg bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
        href="/"
      >
        Return home
      </Link>
    </main>
  );
}
