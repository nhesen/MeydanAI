"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/layout/BrandMark";
import { DesktopSidebar } from "@/components/layout/DesktopSidebar";
import { MobileHeader } from "@/components/layout/MobileHeader";
import { MobileNavigation } from "@/components/layout/MobileNavigation";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  if (pathname.startsWith("/join/")) {
    return (
      <div className="min-h-dvh bg-canvas">
        <header className="flex h-16 items-center border-b border-border bg-surface px-4">
          <div className="mx-auto w-full max-w-lg">
            <BrandMark />
          </div>
        </header>
        <main>{children}</main>
      </div>
    );
  }

  return (
    <>
      <DesktopSidebar />
      <div className="min-h-dvh min-w-0 lg:pl-64">
        <MobileHeader />
        <main className="min-w-0 pb-[calc(5rem+env(safe-area-inset-bottom))] lg:pb-0">
          {children}
        </main>
      </div>
      <MobileNavigation />
    </>
  );
}
