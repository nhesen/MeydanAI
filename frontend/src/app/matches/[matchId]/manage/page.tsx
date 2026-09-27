import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { MatchManagement } from "@/features/matches/components/MatchManagement";

interface MatchManagePageProps {
  params: Promise<{ matchId: string }>;
}

export default async function MatchManagePage({ params }: MatchManagePageProps) {
  const { matchId } = await params;
  return (
    <PageContainer className="max-w-5xl">
      <PageHeader
        description="Review player entries, correct mappings and preserve jersey history."
        eyebrow="Organizer"
        title="Manage match"
      />
      <div className="mt-6 sm:mt-8">
        <MatchManagement matchId={matchId} />
      </div>
    </PageContainer>
  );
}
