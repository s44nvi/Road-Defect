"use client";

import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useMyReports } from "@/components/my-reports/use-my-reports";
import { MyReportCard } from "@/components/my-reports/my-report-card";
import { MyReportsEmptyState } from "@/components/my-reports/empty-state";

function MyReportsContent({ name, token }: { name: string; token: string }) {
  const reportsState = useMyReports(token);

  return (
    <CitizenShell name={name}>
      <PageContainer className="space-y-6 py-8">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">My reports</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Reports you&apos;ve submitted with a photo, and their current progress.
          </p>
        </div>

        {reportsState.status === "loading" ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">Loading your reports…</p>
          </Card>
        ) : reportsState.status === "error" ? (
          <Card className="p-8 text-center">
            <p className="text-sm text-on-surface-variant">
              Couldn&apos;t load your reports: {reportsState.message}
            </p>
            <Button variant="secondary" className="mt-3" onClick={reportsState.reload}>
              Retry
            </Button>
          </Card>
        ) : reportsState.defects.length === 0 ? (
          <MyReportsEmptyState />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {[...reportsState.defects]
              .sort((a, b) => b.defect_id - a.defect_id)
              .map((defect) => (
                <MyReportCard key={defect.defect_id} defect={defect} />
              ))}
          </div>
        )}
      </PageContainer>
    </CitizenShell>
  );
}

export default function MyReportsPage() {
  return (
    <RequireSession role="citizen">
      {(session) => <MyReportsContent name={session.name} token={session.token} />}
    </RequireSession>
  );
}
