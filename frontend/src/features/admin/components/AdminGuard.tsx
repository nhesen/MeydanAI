"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/features/auth/AuthProvider";

export function AdminGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <PageContainer>
        <LoadingSkeleton label="Checking administrator access" lines={4} />
      </PageContainer>
    );
  }

  if (!user) {
    return (
      <PageContainer className="max-w-xl">
        <Card>
          <ErrorState
            message="Sign in with an administrator account to continue."
            title="Authentication required"
          />
          <Link
            className="mt-4 inline-flex min-h-11 items-center rounded-xl bg-brand-700 px-4 text-sm font-semibold text-white"
            href="/login"
          >
            Sign in
          </Link>
        </Card>
      </PageContainer>
    );
  }

  if (user.role !== "admin") {
    return (
      <PageContainer className="max-w-xl">
        <ErrorState
          message="This area is limited to administrators."
          title="Access denied"
        />
      </PageContainer>
    );
  }

  return children;
}
