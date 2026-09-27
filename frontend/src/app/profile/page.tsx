"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { EmptyState } from "@/components/feedback/EmptyState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/features/auth/AuthProvider";

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <PageContainer className="max-w-2xl">
        <LoadingSkeleton label="Loading profile" lines={4} />
      </PageContainer>
    );
  }

  if (!user) {
    return (
      <PageContainer className="max-w-2xl">
        <PageHeader
          description="Sign in to see your account identity and role."
          eyebrow="Account"
          title="Profile"
        />
        <Card className="mt-6" padding="none">
          <EmptyState
            description="Authentication is required to view account details."
            title="You are signed out"
          />
          <div className="flex gap-3 px-5 pb-5">
            <Button onClick={() => router.push("/login")}>Sign in</Button>
            <Button onClick={() => router.push("/register")} variant="secondary">
              Create account
            </Button>
          </div>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer className="max-w-2xl">
      <PageHeader
        description="Account identity and role. Capability tokens are never shown here."
        eyebrow="Account"
        title="Profile"
      />
      <Card className="mt-6 sm:mt-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-lg font-bold text-slate-950">{user.email}</p>
            <p className="mt-1 text-sm text-slate-500">Signed-in account</p>
          </div>
          <Badge>{user.role === "admin" ? "Admin" : "User"}</Badge>
        </div>
        <dl className="mt-6 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Linked player
            </dt>
            <dd className="mt-1 text-sm font-semibold text-slate-800">
              {user.player_id ? (
                <Link className="text-brand-700" href={`/players/${user.player_id}`}>
                  View player profile
                </Link>
              ) : (
                "Not linked"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Member since
            </dt>
            <dd className="mt-1 text-sm font-semibold text-slate-800">
              {new Date(user.created_at).toLocaleDateString()}
            </dd>
          </div>
        </dl>
        <div className="mt-6 flex flex-wrap gap-3">
          {user.role === "admin" ? (
            <Button onClick={() => router.push("/admin")} variant="secondary">
              Open admin
            </Button>
          ) : null}
          <Button
            onClick={() => {
              void logout().then(() => router.push("/login"));
            }}
            variant="destructive"
          >
            Sign out
          </Button>
        </div>
      </Card>
    </PageContainer>
  );
}
