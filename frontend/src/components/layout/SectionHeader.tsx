import type { ReactNode } from "react";

interface SectionHeaderProps {
  id?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function SectionHeader({
  action,
  description,
  id,
  title,
}: SectionHeaderProps) {
  return (
    <div className="flex min-w-0 items-start justify-between gap-4">
      <div className="min-w-0">
        <h2 className="type-section-title text-slate-950" id={id}>
          {title}
        </h2>
        {description ? (
          <p className="mt-1 text-sm leading-6 text-slate-500">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
