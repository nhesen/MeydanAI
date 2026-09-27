import { JoinMatchWizard } from "@/features/join/components/JoinMatchWizard";

interface JoinPageProps {
  params: Promise<{ token: string }>;
}

export default async function JoinPage({ params }: JoinPageProps) {
  const { token } = await params;
  return <JoinMatchWizard token={token} />;
}
