import type { LucideIcon } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";

interface FoundationPageProps {
  eyebrow: string;
  title: string;
  description: string;
  emptyTitle: string;
  emptyDescription: string;
  icon: LucideIcon;
}

export function FoundationPage({
  description,
  emptyDescription,
  emptyTitle,
  eyebrow,
  icon,
  title,
}: FoundationPageProps) {
  return (
    <PageContainer>
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <Card className="mt-6 sm:mt-8" padding="none">
        <EmptyState
          description={emptyDescription}
          icon={icon}
          title={emptyTitle}
        />
      </Card>
    </PageContainer>
  );
}
