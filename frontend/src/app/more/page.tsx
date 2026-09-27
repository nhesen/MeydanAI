import { Clapperboard, Settings, Shield, UserRound } from "lucide-react";

import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { QuickLinkCard } from "@/features/foundation/components/QuickLinkCard";

export default function MorePage() {
  return (
    <PageContainer>
      <PageHeader
        description="Open additional product areas and account options."
        eyebrow="Navigation"
        title="More"
      />
      <div className="mt-6 grid gap-3 sm:mt-8 sm:grid-cols-2">
        <QuickLinkCard
          description="Browse squads and team activity."
          href="/teams"
          icon={Shield}
          title="Teams"
        />
        <QuickLinkCard
          description="Review important match moments."
          href="/highlights"
          icon={Clapperboard}
          title="Highlights"
        />
        <QuickLinkCard
          description="Open your football identity."
          href="/profile"
          icon={UserRound}
          title="Profile"
        />
        <QuickLinkCard
          description="Manage product preferences."
          href="/settings"
          icon={Settings}
          title="Settings"
        />
        <QuickLinkCard
          description="Sign in or create an account."
          href="/login"
          icon={UserRound}
          title="Sign in"
        />
      </div>
    </PageContainer>
  );
}
