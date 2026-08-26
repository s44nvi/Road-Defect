import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { CheckCircleIcon } from "@/components/icons";
import { AIAnalysisSection } from "@/components/incident/ai-analysis-section";
import { defectTypeLabel } from "@/lib/defect-types";
import type { ImageReportResponse } from "@/lib/api";

// Every field shown here comes directly off the ImageReportResponse the
// backend returned from POST /reports/image — nothing here is invented.
// The backend always creates a new row, so there's no duplicate/merge
// state to special-case.
export function ReportSuccess({ defect }: { defect: ImageReportResponse }) {
  return (
    <Card className="mx-auto max-w-lg p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <CheckCircleIcon className="h-7 w-7" />
      </div>
      <h1 className="mt-4 text-xl font-semibold text-on-surface">Report submitted</h1>
      <p className="mt-2 text-sm text-on-surface-variant">
        Thank you for helping improve Mumbai&apos;s roads.
      </p>

      <div className="mt-6 space-y-2 rounded-lg bg-surface-container-low p-4 text-left text-sm">
        <div className="flex items-center justify-between">
          <span className="text-on-surface-variant">Report ID</span>
          <span className="font-medium text-on-surface">#{defect.defect_id}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-on-surface-variant">Type</span>
          <span className="font-medium text-on-surface">{defectTypeLabel(defect.defect_type)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-on-surface-variant">Severity</span>
          <SeverityBadge severity={defect.defect_severity} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-on-surface-variant">Location</span>
          <span className="font-medium text-on-surface">
            {defect.latitude.toFixed(5)}, {defect.longitude.toFixed(5)}
          </span>
        </div>
      </div>

      <div className="mt-4 text-left">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
          AI Analysis
        </p>
        <AIAnalysisSection />
      </div>

      <div className="mt-6 flex flex-col gap-2 sm:flex-row">
        <Link href={`/my-reports/${defect.defect_id}`} className="flex-1">
          <Button variant="secondary" className="w-full">
            View Report
          </Button>
        </Link>
        <Link href="/home" className="flex-1">
          <Button variant="primary" className="w-full">
            Back to Home
          </Button>
        </Link>
      </div>
    </Card>
  );
}
