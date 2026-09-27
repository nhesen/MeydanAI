import type { ReactNode } from "react";

import { DesktopSidebar } from "@/components/layout/DesktopSidebar";
import { MobileHeader } from "@/components/layout/MobileHeader";
import { MobileNavigation } from "@/components/layout/MobileNavigation";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
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
