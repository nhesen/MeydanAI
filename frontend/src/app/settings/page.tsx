import { Settings } from "lucide-react";

import { FoundationPage } from "@/features/foundation/components/FoundationPage";

export default function SettingsPage() {
  return (
    <FoundationPage
      description="Product preferences and account controls will live here."
      emptyDescription="Settings will become available as user preferences are introduced."
      emptyTitle="No settings to configure yet"
      eyebrow="Preferences"
      icon={Settings}
      title="Settings"
    />
  );
}
