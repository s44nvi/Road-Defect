"use client";

import { useState } from "react";
import { RequireSession } from "@/components/auth/require-session";
import { CitizenShell } from "@/components/layout/citizen-shell";
import { PageContainer } from "@/components/layout/page-container";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertIcon } from "@/components/icons";
import { ImageUpload, type ImageUploadValue } from "@/components/report/image-upload";
import { LocationPicker, type Coordinates } from "@/components/report/location-picker";
import { DefectTypeSelect } from "@/components/report/defect-type-select";
import { SeveritySelect } from "@/components/report/severity-select";
import { ReportSuccess } from "@/components/report/report-success";
import { AIAnalysisSection } from "@/components/incident/ai-analysis-section";
import { submitImageReport, ApiError, type ImageReportResponse } from "@/lib/api";
import type { DefectTypeKey } from "@/lib/defect-types";
import type { Severity } from "@/components/ui/severity-badge";

interface FieldErrors {
  image?: string;
  defectType?: string;
  severity?: string;
  location?: string;
}

function ReportForm({ token }: { token: string }) {
  const [image, setImage] = useState<ImageUploadValue | null>(null);
  // Kept as manual fields for now — POST /reports/image classifies the
  // defect itself (that's the point of the pipeline), but its response
  // doesn't echo a defect_type/severity choice back, and the backend
  // currently 503s before ever reaching that stage (see the catch below).
  // Once the detector is live end-to-end, revisit whether these selects
  // are still needed or should become read-only confirmations of the
  // model's own classification.
  const [defectType, setDefectType] = useState<DefectTypeKey | null>(null);
  const [severity, setSeverity] = useState<Severity | null>(null);
  const [location, setLocation] = useState<Coordinates | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<ImageReportResponse | null>(null);

  if (result) {
    return <ReportSuccess defect={result} />;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const errors: FieldErrors = {};
    if (!image) errors.image = "Add a photo of the issue to continue.";
    if (!defectType) errors.defectType = "Select what kind of issue this is.";
    if (!severity) errors.severity = "Select how severe this looks.";
    if (!location) errors.location = "Set a location for this report.";
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const defect = await submitImageReport(
        { latitude: location!.latitude, longitude: location!.longitude, file: image!.file },
        token,
      );
      setResult(defect);
    } catch (error) {
      if (error instanceof ApiError && error.status === 503) {
        // Documented, expected state: backend/app/main.py's /reports/image
        // route raises ModelUnavailableError until the pothole detector is
        // wired in, and returns 503 with no fake inference result. Show
        // that honestly rather than retrying silently or fabricating one.
        setSubmitError(
          "Photo-based reporting isn't available yet — the detection model hasn't been connected on the backend. Please try again later.",
        );
      } else {
        setSubmitError(
          error instanceof ApiError
            ? error.message
            : "Something went wrong submitting your report. Please try again.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="p-6">
          <h2 className="text-base font-semibold text-on-surface">Road issue evidence</h2>
          <div className="mt-4">
            <ImageUpload value={image} onChange={setImage} />
            {fieldErrors.image && <p className="mt-2 text-xs text-error">{fieldErrors.image}</p>}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="text-base font-semibold text-on-surface">Location</h2>
          <div className="mt-4">
            <LocationPicker value={location} onChange={setLocation} />
            {fieldErrors.location && (
              <p className="mt-2 text-xs text-error">{fieldErrors.location}</p>
            )}
          </div>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="text-base font-semibold text-on-surface">AI Analysis</h2>
        <p className="mt-1 text-xs text-on-surface-variant">
          RoadSense can automatically detect the issue type and severity from your photo once ML
          analysis is connected.
        </p>
        <div className="mt-4">
          <AIAnalysisSection />
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="text-base font-semibold text-on-surface">What did you spot?</h2>
        <div className="mt-4">
          <DefectTypeSelect value={defectType} onChange={setDefectType} />
          {fieldErrors.defectType && (
            <p className="mt-2 text-xs text-error">{fieldErrors.defectType}</p>
          )}
        </div>
      </Card>

      <Card className="p-6">
        <h2 className="text-base font-semibold text-on-surface">How severe does this look?</h2>
        <div className="mt-4">
          <SeveritySelect value={severity} onChange={setSeverity} />
          {fieldErrors.severity && (
            <p className="mt-2 text-xs text-error">{fieldErrors.severity}</p>
          )}
        </div>
      </Card>

      {submitError && (
        <div className="flex items-start gap-3 rounded-lg border border-error/30 bg-error-container px-4 py-3 text-sm text-on-error-container">
          <AlertIcon className="mt-0.5 h-4 w-4 shrink-0" />
          <p>{submitError}</p>
        </div>
      )}

      <div className="flex items-center justify-between gap-4 rounded-lg bg-surface-container-low px-4 py-3">
        <p className="text-xs text-on-surface-variant">
          Your report will be reviewed by a municipal officer before action is taken.
        </p>
        <Button type="submit" variant="primary" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit Report"}
        </Button>
      </div>
    </form>
  );
}

function ReportPageContent({ name, token }: { name: string; token: string }) {
  return (
    <CitizenShell name={name}>
      <PageContainer className="space-y-6 py-8">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">Report a Road Issue</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            Help RoadSense identify problems on Mumbai&apos;s roads.
          </p>
        </div>
        <ReportForm token={token} />
      </PageContainer>
    </CitizenShell>
  );
}

export default function ReportIssuePage() {
  return (
    <RequireSession role="citizen">
      {(session) => <ReportPageContent name={session.name} token={session.token} />}
    </RequireSession>
  );
}
