import { UsersRound } from "lucide-react";

import { FoundationPage } from "@/features/foundation/components/FoundationPage";

export default function PlayersPage() {
  return (
    <FoundationPage
      description="Player profiles and match-specific performance will be organized here."
      emptyDescription="Player profiles will appear after participants are added to a match."
      emptyTitle="No players yet"
      eyebrow="Performance"
      icon={UsersRound}
      title="Players"
    />
  );
}
