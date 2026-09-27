import { ArrowRight, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/Card";

interface QuickLinkCardProps {
  href: string;
  title: string;
  description: string;
  icon: LucideIcon;
}

export function QuickLinkCard({
  description,
  href,
  icon: Icon,
  title,
}: QuickLinkCardProps) {
  return (
    <Card padding="none" className="h-full transition-colors hover:border-brand-200">
      <Link
        className="group flex h-full min-w-0 items-start gap-4 rounded-2xl p-5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700 sm:p-6"
        href={href}
      >
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-700">
          <Icon className="size-5" strokeWidth={1.8} aria-hidden="true" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold text-slate-950">{title}</span>
          <span className="mt-1 block text-sm leading-5 text-slate-500">
            {description}
          </span>
        </span>
        <ArrowRight
          className="mt-1 size-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-700"
          aria-hidden="true"
        />
      </Link>
    </Card>
  );
}
