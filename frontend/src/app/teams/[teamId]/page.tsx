import { TeamDetailExperience } from "@/features/platform/components/TeamDetailExperience";

interface TeamDetailPageProps {
  params: Promise<{ teamId: string }>;
}

export default async function TeamDetailPage({ params }: TeamDetailPageProps) {
  const { teamId } = await params;
  return <TeamDetailExperience teamId={teamId} />;
}
