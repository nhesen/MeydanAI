import { UserRound } from "lucide-react";

import { FoundationPage } from "@/features/foundation/components/FoundationPage";

export default function ProfilePage() {
  return (
    <FoundationPage
      description="Your account and football identity will be managed here."
      emptyDescription="Profile management will become available with authentication."
      emptyTitle="Profile setup is coming later"
      eyebrow="Account"
      icon={UserRound}
      title="Profile"
    />
  );
}
