import { PlayerMatchDetail } from "@/features/matches/components/PlayerMatchDetail";

interface PlayerMatchPageProps {
  params: Promise<{ matchId: string; playerId: string }>;
}

export default async function PlayerMatchPage({ params }: PlayerMatchPageProps) {
  const { matchId, playerId } = await params;
  return <PlayerMatchDetail matchId={matchId} playerId={playerId} />;
}
