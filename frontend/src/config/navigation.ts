import {
  BarChart3,
  CalendarDays,
  Clapperboard,
  Ellipsis,
  House,
  Settings,
  Shield,
  UserRound,
  UsersRound,
  type LucideIcon,
} from "lucide-react";

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const primaryNavigation: NavigationItem[] = [
  { label: "Home", href: "/", icon: House },
  { label: "Matches", href: "/matches", icon: CalendarDays },
  { label: "Players", href: "/players", icon: UsersRound },
  { label: "Teams", href: "/teams", icon: Shield },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Highlights", href: "/highlights", icon: Clapperboard },
];

export const accountNavigation: NavigationItem[] = [
  { label: "Profile", href: "/profile", icon: UserRound },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const mobileNavigation: NavigationItem[] = [
  primaryNavigation[0],
  primaryNavigation[1],
  primaryNavigation[2],
  primaryNavigation[4],
  { label: "More", href: "/more", icon: Ellipsis },
];
