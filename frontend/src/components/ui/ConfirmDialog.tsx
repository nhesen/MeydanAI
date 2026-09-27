"use client";

import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/Button";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  busy = false,
  confirmLabel = "Confirm",
  danger = false,
  description,
  onCancel,
  onConfirm,
  open,
  title,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onCancel();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel, open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        aria-label="Close dialog"
        className="absolute inset-0 bg-slate-950/40"
        onClick={onCancel}
        type="button"
      />
      <div
        aria-describedby="confirm-dialog-description"
        aria-labelledby="confirm-dialog-title"
        aria-modal="true"
        className="relative w-full max-w-md rounded-2xl border border-border bg-white p-5 shadow-card"
        role="dialog"
      >
        <h2 className="text-lg font-bold text-slate-950" id="confirm-dialog-title">
          {title}
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-600" id="confirm-dialog-description">
          {description}
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <Button onClick={onCancel} variant="secondary">
            Cancel
          </Button>
          <Button
            loading={busy}
            onClick={onConfirm}
            ref={confirmRef}
            variant={danger ? "destructive" : "primary"}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
