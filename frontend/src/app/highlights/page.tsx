import { Clapperboard } from "lucide-react";

import { FoundationPage } from "@/features/foundation/components/FoundationPage";

export default function HighlightsPage() {
  return (
    <FoundationPage
      description="Important match moments will be collected in a focused viewing experience."
      emptyDescription="Manual and AI-assisted match moments will appear here in a later phase."
      emptyTitle="No highlights yet"
      eyebrow="Match moments"
      icon={Clapperboard}
      title="Highlights"
    />
  );
}
