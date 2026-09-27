import { BarChart3 } from "lucide-react";

import { FoundationPage } from "@/features/foundation/components/FoundationPage";

export default function AnalyticsPage() {
  return (
    <FoundationPage
      description="Rankings, movement trends and comparisons will be presented without fake precision."
      emptyDescription="Analytics will appear after real match and movement data has been processed."
      emptyTitle="No analytics available"
      eyebrow="Insights"
      icon={BarChart3}
      title="Analytics"
    />
  );
}
