"use client";

import { useEffect, useState } from "react";

import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { AdminGuard } from "@/features/admin/components/AdminGuard";
import { AdminShell } from "@/features/admin/components/AdminShell";
import { api } from "@/services/api-client";
import type { AuthUser, UserRole } from "@/types/api";

export function AdminUsersExperience() {
  const [users, setUsers] = useState<AuthUser[]>([]);
  const [failed, setFailed] = useState(false);
  const [pending, setPending] = useState<AuthUser | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    await Promise.resolve();
    try {
      const response = await api.getAdminUsers({ page_size: 50 });
      setUsers(response.data.items);
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }

  useEffect(() => {
    async function initialize() {
      await Promise.resolve();
      try {
        const response = await api.getAdminUsers({ page_size: 50 });
        setUsers(response.data.items);
        setFailed(false);
      } catch {
        setFailed(true);
      }
    }
    void initialize();
  }, []);

  async function changeRole() {
    if (!pending) return;
    setBusy(true);
    try {
      const nextRole: UserRole = pending.role === "admin" ? "user" : "admin";
      await api.updateUserRole(pending.id, nextRole);
      setPending(null);
      await load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminGuard>
      <AdminShell description="Assign administrator access. Users cannot change their own role." title="Users">
        {failed ? (
          <ErrorState message="Users could not be loaded." onRetry={() => void load()} title="Users unavailable" />
        ) : users.length === 0 ? (
          <LoadingSkeleton label="Loading users" lines={5} />
        ) : (
          <div className="space-y-3">
            {users.map((user) => (
              <Card key={user.id}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-950">{user.email}</p>
                    <p className="mt-1 text-xs text-slate-500">{user.id}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge>{user.role}</Badge>
                    <Button onClick={() => setPending(user)} size="sm" variant="secondary">
                      {user.role === "admin" ? "Make user" : "Make admin"}
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
        <ConfirmDialog
          busy={busy}
          confirmLabel="Change role"
          description={
            pending
              ? `Change ${pending.email} from ${pending.role} to ${pending.role === "admin" ? "user" : "admin"}?`
              : ""
          }
          onCancel={() => setPending(null)}
          onConfirm={() => void changeRole()}
          open={pending !== null}
          title="Change user role"
        />
      </AdminShell>
    </AdminGuard>
  );
}
