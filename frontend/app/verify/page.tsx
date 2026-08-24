"use client";

import { RequireSession } from "@/components/auth/require-session";
import { OfficerShell } from "@/components/layout/officer-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";

export default function VerifyPage() {
  return (
    <RequireSession role="officer">
      {(session) => (
        <OfficerShell name={session.name}>
          <PageContainer className="py-12">
            <Card className="p-8 text-center">
              <p className="text-xs font-semibold uppercase tracking-wide text-primary">RoadSense</p>
              <h1 className="mt-2 text-2xl font-semibold text-on-surface">Verification</h1>
              <p className="mt-2 text-sm text-on-surface-variant">
                The officer confirm / reject workflow is coming in the next phase.
              </p>
            </Card>
          </PageContainer>
        </OfficerShell>
      )}
    </RequireSession>
  );
}
