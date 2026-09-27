import { UserRound } from "lucide-react";
import Link from "next/link";

import { BrandMark } from "@/components/layout/BrandMark";

export function MobileHeader() {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-surface/95 px-4 backdrop-blur-sm lg:hidden">
      <BrandMark />
      <Link
        className="grid size-10 place-items-center rounded-xl text-slate-600 transition-colors hover:bg-subtle hover:text-slate-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700"
        href="/profile"
        aria-label="Open profile"
      >
        <UserRound className="size-5" aria-hidden="true" />
      </Link>
    </header>
  );
}
