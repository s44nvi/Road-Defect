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

/** `GET /defects` and `POST /reports` add the AHP priority score on top of
 * DefectResponse. `defect_priority` is null for JSON-only reports (no
 * detection to score) and only populated for defects created through
 * `POST /reports/image`. Structurally assignable to DefectResponse, so
 * existing call sites that only read the base fields need no changes. */
export interface DefectResponseWithPriority extends DefectResponse {
  defect_priority: number | null;
}

/** `GET /defects/{defect_id}` — DefectResponse plus the road-health link. */
export interface DefectDetailResponse extends DefectResponse {
  road_segment_id: string | null;
  is_test_data?: boolean;
}

export class ApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface ApiFetchInit extends RequestInit {
  /** Attaches `Authorization: Bearer <token>` when provided. */
  token?: string;
}

async function apiFetch<T>(path: string, init?: ApiFetchInit): Promise<T> {
  const { token, headers, ...rest } = init ?? {};
  const finalHeaders = new Headers(headers);
  if (token) finalHeaders.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store", ...rest, headers: finalHeaders });
  } catch {
    throw new ApiError("Could not reach the RoadSense backend.");
  }

  if (!response.ok) {
    // FastAPI error responses are {"detail": "..."} — surface the real
    // backend message when present instead of a generic status line.
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // body wasn't JSON — fall through to the generic message
    }
    throw new ApiError(detail ?? `RoadSense backend returned ${response.status}.`, response.status);
  }

  return (await response.json()) as T;
}

/** GET /defects — all reported road defects (officer dashboard + citizen
 * home/community views, filtered client-side per audience). */
export function fetchDefects(): Promise<DefectResponseWithPriority[]> {
  return apiFetch<DefectResponseWithPriority[]>("/defects");
}

/** GET /defects/{defect_id} — single-defect detail. Public, no auth
 * required (see the live OpenAPI schema's description on this route). */
export function fetchDefect(defectId: number): Promise<DefectDetailResponse> {
  return apiFetch<DefectDetailResponse>(`/defects/${defectId}`);
}

// Mirrors backend/app/schemas.py::ReportCreate field-for-field. This is the
// public, unauthenticated JSON report path — it never associates a citizen
// owner (see submitImageReport() below for the path that does).
export interface ReportCreatePayload {
  defect_type: string;
  defect_severity: string;
  latitude: number;
  longitude: number;
}

/** POST /reports — always creates a new defect row; the backend has no
 * duplicate-merge response today, so callers should not expect one. */
export function submitReport(payload: ReportCreatePayload): Promise<DefectResponseWithPriority> {
  return apiFetch<DefectResponseWithPriority>("/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------
// Officer status/severity updates — both now require
// `Authorization: Bearer <officer access token>` (see officerLogin below).

/** Body of `PATCH /defects/{defect_id}/status` — the officer workflow
 * endpoint with note support. `status` (not `defect_status`) is the field
 * name the backend expects here; `changedBy`/`changed_by` is accepted for
 * backwards compatibility but ignored server-side (the acting officer is
 * always derived from the bearer token). */
export interface DefectStatusChangePayload {
  status: string;
  note?: string;
}

/** PATCH /defects/{defect_id}/status — officer-only, full workflow
 * validation. Requires the officer's bearer token. */
export function updateDefectStatus(
  defectId: number,
  payload: DefectStatusChangePayload,
  token: string,
): Promise<DefectDetailResponse> {
  return apiFetch<DefectDetailResponse>(`/defects/${defectId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    token,
  });
}

/** GET /defects/{defect_id}/status-history — full status timeline, oldest
 * first. Public, no auth required. */
export interface StatusHistoryEntry {
  id: number;
  defect_id: number;
  old_status: string | null;
  new_status: string;
  changed_by: string | null;
  changed_at: string; // ISO 8601
  note: string | null;
}

export function fetchDefectStatusHistory(defectId: number): Promise<StatusHistoryEntry[]> {
  return apiFetch<StatusHistoryEntry[]>(`/defects/${defectId}/status-history`);
}

// ---------------------------------------------------------------------
// Officer / citizen authentication — both real JWT-issuing endpoints as of
// the live backend at BACKEND_ORIGIN. Neither role has a signup flow here;
// accounts are provisioned server-side (officers/citizens tables).

export interface OfficerLoginPayload {
  email: string;
  password: string;
}

export interface OfficerPublic {
  officer_id: number;
  name: string;
  email: string;
  department?: string | null;
}

export interface OfficerLoginResponse {
  access_token: string;
  token_type: string;
  officer: OfficerPublic;
}

/** POST /auth/officer/login — verifies against the `officers` table only. */
export function officerLogin(payload: OfficerLoginPayload): Promise<OfficerLoginResponse> {
  return apiFetch<OfficerLoginResponse>("/auth/officer/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface CitizenLoginPayload {
  email: string;
  password: string;
}

export interface CitizenPublic {
  citizen_id: number;
  name: string;
  email: string;
}

export interface CitizenLoginResponse {
  access_token: string;
  token_type: string;
  citizen: CitizenPublic;
}

/** POST /auth/citizen/login — verifies against the `citizens` table only. */
export function citizenLogin(payload: CitizenLoginPayload): Promise<CitizenLoginResponse> {
  return apiFetch<CitizenLoginResponse>("/auth/citizen/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------
// Citizen "my reports" — user-scoped in the database query, not filtered
// client-side. Requires the citizen's bearer token.
export function fetchMyReports(token: string): Promise<DefectResponseWithPriority[]> {
  return apiFetch<DefectResponseWithPriority[]>("/reports/mine", { token });
}

// ---------------------------------------------------------------------
// Image report pipeline — POST /reports/image is the only path that
// associates a report with an authenticated citizen and the only one that
// runs real detection. Per the backend's own route description: until the
// pothole detector is wired in, this always responds 503
// ("ModelUnavailableError") and *never* returns a fake inference result.
// Callers must surface that 503 as an honest "not available yet" state,
// not retry it silently or fall back to fabricated data.
export interface ImageReportResponse extends DefectDetailResponse {
  defect_priority: number | null;
  image_path: string | null;
}

export interface ImageReportPayload {
  latitude: number;
  longitude: number;
  file: File;
}

/** POST /reports/image — multipart/form-data. Requires the citizen's
 * bearer token (see citizenLogin above). */
export function submitImageReport(
  payload: ImageReportPayload,
  token: string,
): Promise<ImageReportResponse> {
  const form = new FormData();
  form.append("latitude", String(payload.latitude));
  form.append("longitude", String(payload.longitude));
  form.append("file", payload.file);

  // Do not set Content-Type here — the browser must generate the
  // multipart boundary itself; setting it manually breaks the upload.
  return apiFetch<ImageReportResponse>("/reports/image", {
    method: "POST",
    body: form,
    token,
  });
}

// ---------------------------------------------------------------------
// Road health — GET /road-health/segments (GeoJSON) and
// GET /road-health/segments/{id} are both real, live endpoints.

export interface LineStringGeometry {
  type: "LineString";
  coordinates: [number, number][]; // [longitude, latitude], WGS84
}

export type HealthCategory = "healthy" | "needs_attention" | "critical";

// Wire shape of one GeoJSON feature's `properties`, field-for-field from
// SegmentProperties in the live OpenAPI schema (snake_case only — the
// backend also emits duplicate camelCase keys for the same values, which
// are intentionally ignored here rather than modeled twice).
export interface SegmentProperties {
  segment_id: string;
  road_name: string;
  segment_label: string;
  length_km: number;
  health_score: number;
  health_status: string;
  health_color: string;
  total_issues: number;
  active_issues: number;
  resolved_issues: number;
  rejected_issues: number;
  critical_issues: number;
  medium_issues: number;
  low_issues: number;
  geometry_source: string | null;
}

export interface SegmentFeature {
  type: "Feature";
  geometry: LineStringGeometry;
  properties: SegmentProperties;
}

/** GET /road-health/segments response — a GeoJSON FeatureCollection. */
export interface SegmentFeatureCollection {
  type: "FeatureCollection";
  features: SegmentFeature[];
}

export function fetchRoadHealthSegments(): Promise<SegmentFeatureCollection> {
  return apiFetch<SegmentFeatureCollection>("/road-health/segments");
}

/** A defect as exposed on `GET /road-health/segments/{id}`. */
export interface SegmentDefect {
  defect_id: number;
  defect_type: string;
  defect_status: string;
  defect_severity: string;
  latitude: number;
  longitude: number;
  is_active: boolean;
  is_test_data: boolean;
}

/** GET /road-health/segments/{segment_id} response. */
export interface SegmentDetail {
  segment_id: string;
  road_name: string;
  segment_label: string;
  geometry: LineStringGeometry;
  length_km: number;
  geometry_source: string | null;
  health_score: number;
  health_status: string;
  health_color: string;
  total_issues: number;
  active_issues: number;
  resolved_issues: number;
  rejected_issues: number;
  critical_issues: number;
  medium_issues: number;
  low_issues: number;
  active_issue_load: number;
  load_density_per_km: number;
  defects: SegmentDefect[];
}

export function fetchRoadHealthSegment(segmentId: string): Promise<SegmentDetail> {
  return apiFetch<SegmentDetail>(`/road-health/segments/${segmentId}`);
}

// Internal presentation shape consumed by the map/dashboard components
// (components/map/defect-map.tsx, components/dashboard/road-health-*.tsx,
// components/road-health/*.tsx). Kept stable across the GeoJSON migration
// so those components didn't need field-by-field rewrites — see
// components/map/use-road-health.ts for the adapter that builds this from
// a real SegmentFeature.
export interface RoadHealthGeometry {
  type: "LineString";
  coordinates: [number, number][];
}

export interface RoadHealthSegment {
  road_segment_id: string;
  road_name: string;
  health_score: number; // 0-10
  health_category: HealthCategory;
  total_issues: number;
  open_issues: number;
  resolved_issues: number;
  critical_issues: number;
  medium_issues: number;
  low_issues: number;
  geometry: RoadHealthGeometry;
}

// ---------------------------------------------------------------------
// Per-incident AI/evidence fields — still NOT populated by any real
// response. POST /reports/image's ImageReportResponse carries a priority
// score and an image path (both modeled above), but no bounding
// box/confidence/class detail is returned to the frontend anywhere today.
// No call site in this codebase ever constructs a real one — every
// consumer receives `undefined`/`null` and renders an honest "not
// available yet" state instead.
export interface AIDetectionResult {
  detected_class: string;
  confidence: number; // 0-1
  model_source: string;
  bbox?: { x: number; y: number; width: number; height: number };
}
