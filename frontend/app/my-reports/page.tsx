"use client";

import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";

export default function MyReportsPage() {
  return (
    <RequireSession role="citizen">
      {(session) => (
        <CitizenShell name={session.name}>
          <PageContainer className="py-12">
            <Card className="p-8 text-center">
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">RoadSense</p>
              <h1 className="mt-2 text-2xl font-semibold text-on-surface">My reports</h1>
              <p className="mt-2 text-sm text-on-surface-variant">
                Your submitted reports are coming in the next phase.
              </p>
            </Card>
          </PageContainer>
        </CitizenShell>
      )}
    </RequireSession>
  );
}
