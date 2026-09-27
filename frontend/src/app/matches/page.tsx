import { CalendarDays } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/feedback/EmptyState";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/ui/Card";

export default function MatchesPage() {
  return (
    <PageContainer>
      <PageHeader
        action={
          <Link
            className="inline-flex h-11 items-center justify-center rounded-xl bg-brand-700 px-4 text-sm font-semibold text-white transition hover:bg-brand-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700"
            href="/matches/new"
          >
            Create match
          </Link>
        }
        description="Follow scheduled, live, processing and completed games from one place."
        eyebrow="Match center"
        title="Matches"
      />
      <Card className="mt-6 sm:mt-8" padding="none">
        <EmptyState
          description="Create your first match to generate a secure QR join link for players."
          icon={CalendarDays}
          title="No matches yet"
        />
      </Card>
    </PageContainer>
  );
}
