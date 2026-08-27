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

/** Report consolidation ("one physical defect = one municipal record").
 * `report_count` is how many individual citizen observations back this
 * physical defect (>= 1). `canonical_defect_id` is set only on a row that
 * is itself a corroborating observation of another physical defect (used by
 * the citizen "My Reports" view); null on canonical rows. Both are additive
 * — mirrors backend/app/schemas.py. */
export interface ConsolidationFields {
  report_count: number;
  canonical_defect_id: number | null;
}

/** `GET /defects` and `POST /reports` add the AHP priority score on top of
 * DefectResponse. `defect_priority` is null for JSON-only reports (no
 * detection to score) and only populated for defects created through
 * `POST /reports/image`. Structurally assignable to DefectResponse, so
 * existing call sites that only read the base fields need no changes. */
export interface DefectResponseWithPriority extends DefectResponse {
  defect_priority: number | null;
  /** >= 1. Number of citizen observations behind this physical defect. */
  report_count: number;
  /** Set only when this row is a corroborating observation of another
   * physical defect (its own submission, folded into that one). */
  canonical_defect_id: number | null;
}

/** The citizen who submitted a defect, as exposed to officers only (see
 * DefectDetailResponse.reporter). */
export interface ReporterPublic {
  id: number;
  full_name: string;
  email: string;
}

/** `GET /defects/{defect_id}` — DefectResponse plus the road-health link,
 * AI detection metadata, evidence image, and reporter identity. As of
 * backend commit 618fbfe this route is officer-only (it now carries
 * citizen PII via `reporter`) — see fetchDefect() below. */
/** One individual citizen observation backing a physical defect, in the
 * officer's corroboration view. Mirrors backend schemas.ContributingReport. */
export interface ContributingReport {
  report_id: number;
  reported_at: string | null;
  latitude: number;
  longitude: number;
  defect_type: string;
  defect_severity: string;
  image_url: string | null;
  ai_confidence: number | null;
  ai_bbox: [number, number, number, number] | null;
  ai_severity_score: number | null;
  ai_model_source: string | null;
  reporter: ReporterPublic | null;
}

export interface DefectDetailResponse extends DefectResponse {
  road_segment_id: string | null;
  is_test_data?: boolean;
  reporter: ReporterPublic | null;
  ai_confidence: number | null;
  ai_bbox: [number, number, number, number] | null;
  ai_severity_score: number | null;
  defect_priority: number | null;
  image_path: string | null;
  /** Browser-fetchable URL (served under /uploads/...) — null when the
   * defect has no associated image (e.g. JSON-only reports). */
  image_url: string | null;
  /** Consolidation: number of citizen observations behind this physical
   * defect (>= 1), and each of them. `reports[0]` is the canonical row. */
  report_count: number;
  canonical_defect_id: number | null;
  reports: ContributingReport[];
  /** ISO 8601, already converted to Asia/Kolkata by the backend
   * (timezone_utils.to_ist) — still run through lib/format-datetime.ts's
   * formatIST() for display, which works correctly regardless of the
   * offset the string already carries. Null only if a defect somehow has
   * no status history at all. */
  reported_at: string | null;
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

/** GET /defects/{defect_id} — single-defect detail. As of backend commit
 * 618fbfe this is officer-only (the response now includes the reporting
 * citizen's name/email) — requires the officer's bearer token. Citizens
 * viewing their own report use fetchMyReports() + client-side lookup
 * instead (see app/my-reports/[id]/page.tsx). */
export function fetchDefect(defectId: number, token: string): Promise<DefectDetailResponse> {
  return apiFetch<DefectDetailResponse>(`/defects/${defectId}`, { token });
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
// Two-step citizen reporting pipeline (backend commit 618fbfe) —
// POST /reports/analyze (pure AI analysis, never creates a Defect) then
// POST /reports/submit (the citizen's actual final creation step, using
// the image_token from analyze). This finally makes "Analyze" and
// "Submit" two genuinely separate backend calls for every category,
// including Hawker/Encroachment — unlike the older POST /ml/hawkers/detect
// and POST /reports/image, which persist immediately on detection. Both
// require the citizen's bearer token.

/** POST /reports/analyze response. `category`/`confidence`/`bbox` are all
 * `null` together when nothing was confidently detected across either the
 * pothole or hawker detector streams — never a fabricated guess. */
export interface AnalyzeImageResponse {
  image_token: string;
  category: string | null;
  confidence: number | null;
  bbox: [number, number, number, number] | null;
  ai_severity: string | null;
  ai_severity_score: number | null;
  model_source: string | null;
}

export interface AnalyzeImagePayload {
  file: File;
  /** Optional — enables AI severity scoring (Road Intelligence/AHP) when
   * provided; category/confidence/bbox are still returned without it. */
  latitude?: number;
  longitude?: number;
}

export function analyzeReportImage(payload: AnalyzeImagePayload, token: string): Promise<AnalyzeImageResponse> {
  const form = new FormData();
  form.append("file", payload.file);
  if (payload.latitude != null) form.append("latitude", String(payload.latitude));
  if (payload.longitude != null) form.append("longitude", String(payload.longitude));
  return apiFetch<AnalyzeImageResponse>("/reports/analyze", {
    method: "POST",
    body: form,
    token,
  });
}

/** Body of POST /reports/submit. `image_token` must come from a prior
 * analyzeReportImage() call. defect_type/defect_severity are the
 * citizen's final choice — may differ from the AI suggestion; the citizen
 * always has the final say, never silently overridden. */
export interface SubmitReportPayload {
  image_token: string;
  latitude: number;
  longitude: number;
  defect_type: string;
  defect_severity: string;
}

/** POST /reports/submit — the real, final report-creation call. Re-runs
 * detection on the already-persisted image server-side for AI metadata +
 * AHP scoring, but always stores the citizen's chosen category/severity. */
export function submitFinalReport(payload: SubmitReportPayload, token: string): Promise<ImageReportResponse> {
  return apiFetch<ImageReportResponse>("/reports/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    token,
  });
}

// ---------------------------------------------------------------------
// Nearby reports — GET /reports/nearby. Read-only location search with
// real backend-computed haversine distance (road_health.geo.haversine_km),
// never a client-side approximation. Requires the citizen's bearer token.
export interface NearbyIncidentResponse {
  defect_id: number;
  defect_type: string;
  defect_severity: string;
  defect_priority: number | null;
  latitude: number;
  longitude: number;
  distance_km: number;
  defect_status: string;
  reported_at: string | null;
  image_url: string | null;
  road_segment_id: string | null;
  nearest_road: string | null;
  /** Citizen observations behind this physical defect (>= 1). */
  report_count: number;
}

export interface NearbyReportsQuery {
  latitude: number;
  longitude: number;
  radiusKm: number;
}

export function fetchNearbyReports(query: NearbyReportsQuery, token: string): Promise<NearbyIncidentResponse[]> {
  const params = new URLSearchParams({
    latitude: String(query.latitude),
    longitude: String(query.longitude),
    radius_km: String(query.radiusKm),
  });
  return apiFetch<NearbyIncidentResponse[]>(`/reports/nearby?${params.toString()}`, { token });
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
// Now a plain alias — `defect_priority`/`image_path`/`ai_*`/`image_url` all
// live directly on DefectDetailResponse as of backend commit 618fbfe (per
// its own docstring: "this subclass exists only for backwards-compat
// naming/import stability").
export type ImageReportResponse = DefectDetailResponse;

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
  mcgm_id: string | null;
  ward: string | null;
  work_status: string | null;
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

export function fetchRoadHealthSegments(geometrySource?: string): Promise<SegmentFeatureCollection> {
  const qs = geometrySource ? `?geometry_source=${encodeURIComponent(geometrySource)}` : "";
  return apiFetch<SegmentFeatureCollection>(`/road-health/segments${qs}`);
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
  mcgm_id: string | null;
  ward: string | null;
  work_status: string | null;
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

// ---------------------------------------------------------------------
// Hawker / encroachment detection — POST /ml/hawkers/detect. As of the
// current backend contract this call *is* the submission for this
// category, not a separate analyze-then-submit step: it requires the
// citizen's bearer token and location, runs every detection through the
// same Road Intelligence/AHP service as the pothole pipeline, and
// persists one Defect per detection in a single DB transaction (see the
// live OpenAPI description on this route). The frontend must never call
// any other endpoint to "finish" a hawker report after this succeeds —
// doing so would create duplicates.
//
// Real inference only — a failed/empty call must never be papered over
// with a fabricated detection.
export interface HawkerDetectionItem {
  defect_id: number;
  /** One of: fixed-stall-vendor, semi-fixed-vendor, itinerant-vendor —
   * kept exactly as the model returns it for any future internal use, but
   * intentionally never shown in the UI; see
   * components/report/ai-detection.tsx, which always displays a
   * detection as simply "Vendor Detected". */
  class_name: string;
  confidence: number; // 0-1
  /** [x_min, y_min, x_max, y_max] in *original* image pixel coordinates —
   * callers must scale against the source image's natural width/height,
   * never the displayed element size. */
  bbox: [number, number, number, number];
  /** Real, AHP-computed severity — displayed as-is by
   * components/report/ai-detection.tsx (unlike the pothole pipeline,
   * whose response has no confidence/bbox but does share this same
   * real-severity guarantee). */
  defect_severity: string;
  severity_score: number;
  defect_priority: number;
  latitude: number;
  longitude: number;
  road_segment_id: string | null;
  image_path: string;
}

export interface HawkerDetectionResponse {
  filename: string | null;
  detections: HawkerDetectionItem[];
}

export interface HawkerDetectPayload {
  latitude: number;
  longitude: number;
  file: File;
}

/** POST /ml/hawkers/detect — requires the citizen's bearer token. */
export function detectHawkers(payload: HawkerDetectPayload, token: string): Promise<HawkerDetectionResponse> {
  const form = new FormData();
  form.append("latitude", String(payload.latitude));
  form.append("longitude", String(payload.longitude));
  form.append("file", payload.file);
  // No Content-Type here — same reasoning as submitImageReport() above.
  return apiFetch<HawkerDetectionResponse>("/ml/hawkers/detect", {
    method: "POST",
    body: form,
    token,
  });
}

// Internal presentation shape consumed by the map/dashboard components
// (components/map/defect-map.tsx, components/dashboard/road-health-*.tsx,
// components/road-health/*.tsx). Kept stable across the GeoJSON migration
// so those components didn't need field-by-field rewrites — see
// components/map/use-road-health.ts for the adapter that builds this from
// a real SegmentFeature.
export interface RoadHealthLineString {
  type: "LineString";
  coordinates: [number, number][];
}

export interface RoadHealthMultiLineString {
  type: "MultiLineString";
  coordinates: [number, number][][];
}

/** A segment's geometry is either a LineString or a MultiLineString (real
 * MCGM roads may have genuinely disconnected parts). Components that only
 * need to pass it to MapLibre can treat both interchangeably as GeoJSON. */
export type RoadHealthGeometry = RoadHealthLineString | RoadHealthMultiLineString;

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
  /** MCGM source tag; null for OSM / dev segments. */
  geometry_source: string | null;
  /** MCGM road ID (e.g. "MCGM-2353"); null for non-MCGM segments. */
  mcgm_id: string | null;
  /** MCGM ward; null for non-MCGM segments. */
  ward: string | null;
  /** MCGM work status; null for non-MCGM segments. */
  work_status: string | null;
}

// ---------------------------------------------------------------------
// MCGM infrastructure context — GET /road-health/segments/{id}/assets.
// These are purely informational: manholes and encroachments are real
// MCGM datasets but MUST NOT affect Road Health scoring, severity, or
// defect counts (see backend/app/assets/router.py for the separation
// rationale). The frontend renders them as read-only context only.

export interface ManholeItem {
  id: number;
  object_id: string;
  road_name: string | null;
  ward: string | null;
  latitude: number;
  longitude: number;
  status: string | null;
  condition: string | null;
  remarks: string | null;
  road_norm: string | null;
  segment_id: string | null;
}

export interface EncroachmentItem {
  id: number;
  object_id: string | null;
  road_name: string | null;
  ward: string | null;
  latitude: number;
  longitude: number;
  status: string | null;
  complaint_type: string | null;
  description: string | null;
  segment_id: string | null;
}

export interface SegmentAssetsResponse {
  segment_id: string;
  manhole_count: number;
  encroachment_count: number;
  manholes: ManholeItem[];
  encroachments: EncroachmentItem[];
}

/** GET /road-health/segments/{segment_id}/assets — MCGM context layer.
 * Returns manholes and encroachments linked to this segment. Results are
 * context only and must never influence Road Health display. */
export function fetchSegmentAssets(segmentId: string): Promise<SegmentAssetsResponse> {
  return apiFetch<SegmentAssetsResponse>(`/road-health/segments/${segmentId}/assets`);
}

// ---------------------------------------------------------------------
// Per-defect AI/evidence fields (pothole/crack incidents) — still NOT
// populated by any real response. POST /reports/image's ImageReportResponse
// carries a priority score and an image path (both modeled above), but no
// bounding box/confidence/class detail is returned for defects today.
// (Hawker detection above is a separate, unrelated feature that *does*
// return real bbox/confidence/class data — see HawkerDetection.) No call
// site in this codebase ever constructs a real AIDetectionResult — every
// consumer receives `undefined`/`null` and renders an honest "not
// available yet" state instead.
export interface AIDetectionResult {
  detected_class: string;
  confidence: number; // 0-1
  model_source: string;
  bbox?: { x: number; y: number; width: number; height: number };
}
