"use client";

import { BrandMark } from "@/components/layout/BrandMark";
import { NavigationLink } from "@/components/layout/NavigationLink";
import { Divider } from "@/components/ui/Divider";
import { accountNavigation, primaryNavigation } from "@/config/navigation";

export function DesktopSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border bg-surface lg:flex lg:flex-col">
      <div className="flex h-20 items-center px-5">
        <BrandMark />
      </div>

      <nav className="flex-1 px-3 py-4" aria-label="Primary navigation">
        <p className="mb-2 px-3 text-[0.6875rem] font-bold uppercase tracking-[0.12em] text-slate-400">
          Workspace
        </p>
        <div className="space-y-1">
          {primaryNavigation.map((item) => (
            <NavigationLink item={item} key={item.href} />
          ))}
        </div>
      </nav>

      <div className="px-3 pb-4">
        <Divider className="mb-3" />
        <nav className="space-y-1" aria-label="Account navigation">
          {accountNavigation.map((item) => (
            <NavigationLink item={item} key={item.href} />
          ))}
        </nav>
      </div>
    </aside>
  );
}
