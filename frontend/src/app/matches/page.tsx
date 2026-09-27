import { CalendarDays } from "lucide-react";

import { FoundationPage } from "@/features/foundation/components/FoundationPage";

export default function MatchesPage() {
  return (
    <FoundationPage
      description="Follow scheduled, live, processing and completed games from one place."
      emptyDescription="Your analyzed and upcoming matches will appear here when match creation is available."
      emptyTitle="No matches yet"
      eyebrow="Match center"
      icon={CalendarDays}
      title="Matches"
    />
  );
}
