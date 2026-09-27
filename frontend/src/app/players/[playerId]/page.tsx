import { GlobalPlayerProfile } from "@/features/platform/components/GlobalPlayerProfile";

interface PlayerProfilePageProps {
  params: Promise<{ playerId: string }>;
}

export default async function PlayerProfilePage({
  params,
}: PlayerProfilePageProps) {
  const { playerId } = await params;
  return <GlobalPlayerProfile playerId={playerId} />;
}
