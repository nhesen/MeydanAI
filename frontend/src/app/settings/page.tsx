import { Settings } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";

export default function SettingsPage() {
  return (
    <PageContainer>
      <PageHeader
        description="Product preferences and account controls will live here."
        eyebrow="Preferences"
        title="Settings"
      />
      <Card className="mt-6 sm:mt-8" padding="none">
        <EmptyState
          description="Settings will become available as user preferences are introduced."
          icon={Settings}
          title="No settings to configure yet"
        />
      </Card>
    </PageContainer>
  );
}
