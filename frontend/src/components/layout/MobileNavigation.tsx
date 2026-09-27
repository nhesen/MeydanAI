"use client";

import { NavigationLink } from "@/components/layout/NavigationLink";
import { mobileNavigation } from "@/config/navigation";

export function MobileNavigation() {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface/95 px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1 backdrop-blur-sm lg:hidden"
      aria-label="Mobile navigation"
    >
      <div className="mx-auto flex max-w-lg items-stretch">
        {mobileNavigation.map((item) => (
          <NavigationLink item={item} key={item.href} mobile />
        ))}
      </div>
    </nav>
  );
}
