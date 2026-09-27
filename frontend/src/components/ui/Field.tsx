import type { ReactNode } from "react";

interface FieldProps {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

export function Field({
  children,
  error,
  hint,
  htmlFor,
  label,
}: FieldProps) {
  const descriptionId = error || hint ? `${htmlFor}-description` : undefined;
  return (
    <div className="min-w-0">
      <label className="mb-1.5 block text-sm font-semibold text-slate-800" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error || hint ? (
        <p
          className={`mt-1.5 text-xs ${error ? "text-danger-700" : "text-slate-500"}`}
          id={descriptionId}
        >
          {error ?? hint}
        </p>
      ) : null}
    </div>
  );
}
