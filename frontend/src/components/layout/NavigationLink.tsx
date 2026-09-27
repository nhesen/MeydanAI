"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { NavigationItem } from "@/config/navigation";
import { cn } from "@/lib/cn";

interface NavigationLinkProps {
  item: NavigationItem;
  mobile?: boolean;
}

export function NavigationLink({ item, mobile = false }: NavigationLinkProps) {
  const pathname = usePathname();
  const secondaryMobileRoutes = [
    "/teams",
    "/highlights",
    "/profile",
    "/settings",
    "/admin",
    "/login",
    "/register",
  ];
  const active =
    item.href === "/"
      ? pathname === "/"
      : pathname.startsWith(item.href) ||
        (item.href === "/more" &&
          secondaryMobileRoutes.some((route) => pathname.startsWith(route)));
  const Icon = item.icon;

  return (
    <Link
      aria-current={active ? "page" : undefined}
      className={cn(
        "group rounded-xl font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-700",
        mobile
          ? "flex min-w-0 flex-1 flex-col items-center justify-center gap-1 px-1 py-2 text-[0.6875rem]"
          : "flex h-11 items-center gap-3 px-3 text-sm",
        active
          ? "bg-brand-50 text-brand-800"
          : "text-slate-600 hover:bg-subtle hover:text-slate-950",
      )}
      href={item.href}
    >
      <Icon
        className={cn(
          "shrink-0",
          mobile ? "size-5" : "size-[1.125rem]",
          active ? "text-brand-700" : "text-slate-500 group-hover:text-slate-700",
        )}
        strokeWidth={active ? 2.25 : 1.8}
        aria-hidden="true"
      />
      <span className={mobile ? "max-w-full truncate" : "truncate"}>
        {item.label}
      </span>
    </Link>
  );
}
