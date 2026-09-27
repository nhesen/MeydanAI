import { Shield } from "lucide-react";

import { FoundationPage } from "@/features/foundation/components/FoundationPage";

export default function TeamsPage() {
  return (
    <FoundationPage
      description="Keep squads, recent matches and team-level insights easy to scan."
      emptyDescription="Teams will appear here when the first match setup is completed."
      emptyTitle="No teams yet"
      eyebrow="Clubs & squads"
      icon={Shield}
      title="Teams"
    />
  );
}
