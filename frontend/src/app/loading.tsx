import { LoadingSkeleton } from "@/components/feedback/LoadingSkeleton";
import { PageContainer } from "@/components/layout/PageContainer";
import { Card } from "@/components/ui/Card";

export default function Loading() {
  return (
    <PageContainer>
      <div className="max-w-2xl">
        <LoadingSkeleton lines={2} label="Loading page header" />
      </div>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }, (_, index) => (
          <Card key={index}>
            <LoadingSkeleton lines={3} label="Loading content card" />
          </Card>
        ))}
      </div>
    </PageContainer>
  );
}
