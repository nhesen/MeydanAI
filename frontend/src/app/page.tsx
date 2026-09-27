import { BarChart3, CalendarClock, CalendarDays, Shield, UsersRound } from "lucide-react";

import { EmptyState } from "@/components/feedback/EmptyState";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionHeader } from "@/components/layout/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { QuickLinkCard } from "@/features/foundation/components/QuickLinkCard";
import { SystemHealthCard } from "@/features/system-health/components/SystemHealthCard";

export default function Home() {
  return (
    <PageContainer>
      <PageHeader
        eyebrow="Football analytics"
        title="See every match more clearly."
        description="MeydanAI is being built to turn small-sided football into simple, useful performance insights."
      />

      <div className="mt-6 grid min-w-0 gap-5 sm:mt-8 lg:grid-cols-[minmax(0,1.6fr)_minmax(18rem,0.8fr)]">
        <Card className="flex min-h-56 flex-col justify-between overflow-hidden" padding="lg">
          <div>
            <Badge variant="brand">Product foundation</Badge>
            <h2 className="mt-5 max-w-xl text-2xl font-bold tracking-[-0.035em] text-slate-950 sm:text-3xl">
              Built for the pace of small-sided football.
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
              Match results, player movement and performance analytics will
              live in one fast, mobile-first experience.
            </p>
          </div>
          <div className="mt-8 flex flex-wrap gap-2">
            <Badge>Match context</Badge>
            <Badge>Player movement</Badge>
            <Badge>Clear comparisons</Badge>
          </div>
        </Card>
        <SystemHealthCard />
      </div>

      <section className="mt-8 sm:mt-10" aria-labelledby="quick-links-heading">
        <SectionHeader
          id="quick-links-heading"
          title="Explore MeydanAI"
          description="The core product areas are ready for upcoming analytics features."
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <QuickLinkCard
            description="Browse upcoming and analyzed games."
            href="/matches"
            icon={CalendarDays}
            title="Matches"
          />
          <QuickLinkCard
            description="Find player profiles and performances."
            href="/players"
            icon={UsersRound}
            title="Players"
          />
          <QuickLinkCard
            description="View squads and team activity."
            href="/teams"
            icon={Shield}
            title="Teams"
          />
          <QuickLinkCard
            description="Open rankings, trends and comparisons."
            href="/analytics"
            icon={BarChart3}
            title="Analytics"
          />
        </div>
      </section>

      <section className="mt-8 sm:mt-10" aria-labelledby="recent-activity-heading">
        <SectionHeader
          id="recent-activity-heading"
          title="Recent activity"
          description="Your latest analyzed matches will appear here."
        />
        <Card className="mt-4" padding="none">
          <EmptyState
            compact
            description="Once a match has been added and processed, its score and key insights will be easy to revisit."
            icon={CalendarClock}
            title="No match activity yet"
          />
        </Card>
      </section>
    </PageContainer>
  );
}
