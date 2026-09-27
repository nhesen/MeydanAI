import Link from "next/link";

import { cn } from "@/lib/cn";

export interface TabItem {
  id: string;
  label: string;
  href: string;
}

interface TabsProps {
  items: TabItem[];
  activeId: string;
  label: string;
}

export function Tabs({ activeId, items, label }: TabsProps) {
  return (
    <div
      className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0"
      aria-label={label}
      role="tablist"
    >
      <div className="flex min-w-max border-b border-border">
        {items.map((item) => {
          const active = item.id === activeId;
          return (
            <Link
              aria-selected={active}
              className={cn(
                "relative flex h-12 items-center px-4 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand-700",
                active
                  ? "text-brand-800 after:absolute after:inset-x-3 after:bottom-0 after:h-0.5 after:rounded-full after:bg-brand-700"
                  : "text-slate-500 hover:text-slate-900",
              )}
              href={item.href}
              key={item.id}
              role="tab"
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
