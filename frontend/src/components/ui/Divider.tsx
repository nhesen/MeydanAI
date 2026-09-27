import { cn } from "@/lib/cn";

interface DividerProps {
  className?: string;
}

export function Divider({ className }: DividerProps) {
  return <div className={cn("h-px w-full bg-border", className)} role="separator" />;
}
