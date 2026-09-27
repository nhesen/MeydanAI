import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { MatchCreateForm } from "@/features/matches/components/MatchCreateForm";

export default function NewMatchPage() {
  return (
    <PageContainer className="max-w-5xl">
      <PageHeader
        description="Set the time, venue and two teams. A secure player join link will be created automatically."
        eyebrow="Organizer"
        title="Create match"
      />
      <div className="mt-6 sm:mt-8">
        <MatchCreateForm />
      </div>
    </PageContainer>
  );
}
