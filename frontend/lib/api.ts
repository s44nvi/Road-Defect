/** Single boundary for frontend calls to the backend API. */

export const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL ?? "/api";

// Mirrors backend/app/schemas.py::DefectResponse field-for-field.
// defect_status and defect_severity are plain strings on the backend
// (SQLAlchemy String columns, not enums), so they are typed loosely here
// too — normalize/validate values at the UI edge (see lib/defect-types.ts
// and components/ui/severity-badge.tsx) rather than trusting the wire shape.
export interface DefectResponse {
  defect_id: number;
  defect_type: string;
  defect_status: string;
  defect_severity: string;
  latitude: number;
  longitude: number;
}

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError("Could not reach the RoadSense backend.");
  }

  if (!response.ok) {
    throw new ApiError(`RoadSense backend returned ${response.status}.`, response.status);
  }

  return (await response.json()) as T;
}

/** GET /defects — all reported road defects. */
export function fetchDefects(): Promise<DefectResponse[]> {
  return apiFetch<DefectResponse[]>("/defects");
}

// Mirrors backend/app/schemas.py::ReportCreate field-for-field. Note there
// is no image/file field on this contract — POST /reports only accepts
// these four values. See components/report/image-upload.tsx for how the
// photo is handled (kept local-only; not sent here) until the backend
// exposes somewhere to send it.
export interface ReportCreatePayload {
  defect_type: string;
  defect_severity: string;
  latitude: number;
  longitude: number;
}

/** POST /reports — always creates a new defect row; the backend has no
 * duplicate-merge response today, so callers should not expect one. */
export function submitReport(payload: ReportCreatePayload): Promise<DefectResponse> {
  return apiFetch<DefectResponse>("/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// Mirrors backend/app/schemas.py::DefectStatusUpdate field-for-field.
export interface DefectStatusUpdatePayload {
  defect_status: string;
}

/** PATCH /defects/{defect_id} — persists the new status in PostgreSQL and
 * returns the updated row. 404s (via ApiError.status) if the id doesn't exist. */
export function updateDefectStatus(
  defectId: number,
  payload: DefectStatusUpdatePayload,
): Promise<DefectResponse> {
  return apiFetch<DefectResponse>(`/defects/${defectId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
