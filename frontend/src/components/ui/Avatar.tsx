import { cn } from "@/lib/cn";

interface AvatarProps {
  name: string;
  className?: string;
}

export function Avatar({ className, name }: AvatarProps) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <span
      className={cn(
        "grid size-10 shrink-0 place-items-center rounded-full bg-brand-100 text-xs font-bold text-brand-800",
        className,
      )}
      aria-hidden="true"
    >
      {initials || "?"}
    </span>
  );
}
