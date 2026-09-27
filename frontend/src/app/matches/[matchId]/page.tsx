import { MatchDetailExperience } from "@/features/matches/components/MatchDetailExperience";

interface MatchDetailPageProps {
  params: Promise<{ matchId: string }>;
}

export default async function MatchDetailPage({ params }: MatchDetailPageProps) {
  const { matchId } = await params;
  return <MatchDetailExperience matchId={matchId} />;
}
