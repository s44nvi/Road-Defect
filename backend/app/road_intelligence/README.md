# Road Intelligence Module

Deterministic, explainable **Severity Estimation** + **AHP Priority Scoring**
for road-defect detections coming out of a YOLO pipeline.

```
YOLO Detection → Severity Estimation → Severity Score → AHP Priority Scoring → Priority Score → FastAPI → PostgreSQL
```

> **⚠️ Built without repository access.** This module was implemented as a
> standalone package, not by inspecting an actual codebase — no repo was
> available. Every place that depends on real-world specifics (YOLO class
> names, road classification scheme, existing DB/route structure) is
> clearly marked below and in `config.py`, with a documented, sensible
> placeholder. **A developer must review the "Adapt before production
> use" section before wiring this into a real backend.**

---

## 1. What severity means

`severity_score` (0–100) is a **relative, explainable indicator** of how
urgently a single detected defect needs attention, derived only from
signals a YOLO detector can actually produce: **defect class, detection
confidence, and bounding-box geometry**. It is *not* a physical
measurement of pothole depth/volume, and it is *not* a calibrated,
validated accuracy metric — no ground-truth severity labels were
available to validate against, so none are claimed.

## 2. Severity formula

```
severity_raw = w1 · defect_type_score
             + w2 · size_score
             + w3 · dimension_score
             + w4 · confidence_score

severity_score = clip(severity_raw × 100, 0, 100)
```

All four component scores are normalized to `[0, 1]` before weighting, so
the formula is guaranteed to stay within `[0, 100]` — no post-hoc
clamping surprises.

| Component | What it captures | Source |
|---|---|---|
| `defect_type_score` | Intrinsic risk of this class of defect (pothole vs hairline crack) | `config.DEFECT_TYPE_BASE_SEVERITY[class_name]` |
| `size_score` | How much of the visible road surface is affected | `bbox_area / image_area`, saturating at `config.SIZE_SATURATION_RATIO` |
| `dimension_score` | How far the defect extends across the frame (catches long/elongated cracks that area alone under-represents) | `max(bbox_width/image_width, bbox_height/image_height)`, saturating at `config.DIMENSION_SATURATION_RATIO` |
| `confidence_score` | Strength of detection evidence (deliberately lowest weight — this is detector certainty, not real-world severity) | YOLO `confidence`, used directly |

**Documented limitation:** bounding-box area is a 2D pixel-space proxy
for the detection box, not the true physical surface area of the
defect — a pothole's real damaged area is usually smaller than, and a
different shape than, its bbox, and pixel area also depends on camera
distance/angle. Treat `size_score`/`dimension_score` as ordinal severity
signals, not measurements.

## 3. Severity weights

Defined once in `config.SEVERITY_WEIGHTS` (sum to exactly 1.0):

| Weight | Value | Rationale |
|---|---|---|
| `defect_type` | 0.35 | Intrinsic risk is the strongest single severity signal |
| `size` | 0.30 | Larger affected area is close behind class in intuitive severity |
| `dimension` | 0.20 | Secondary geometric signal, catches elongated defects |
| `confidence` | 0.15 | Nudges score with detector certainty; should not dominate |

## 4. Severity categories

`config.SEVERITY_CATEGORY_THRESHOLDS` (inclusive bounds, no gaps/overlaps):

| Range | Category |
|---|---|
| 0–24 | Low |
| 25–49 | Medium |
| 50–74 | High |
| 75–100 | Critical |

## 5. AHP criteria

| Code | Criterion | Source | Required? |
|---|---|---|---|
| C1 | `severity` | `severity_score` from step above | Always available (computed) |
| C2 | `size` | `bbox_area_ratio` (reused from severity geometry) | Available if `image_width`/`image_height` given, else fallback |
| C3 | `traffic_criticality` | `context.traffic_criticality` (0–1) or `context.road_type` mapped via `config.ROAD_TYPE_CRITICALITY` | Optional, documented fallback |
| C4 | `recurrence` | `context.recurrence_count` (defects seen in same segment) | Optional, documented fallback |
| C5 | `location_criticality` | `context.location_criticality` (0–1, pre-computed by backend/GIS — proximity to schools/hospitals/junctions) | Optional, documented fallback — **this module has no infrastructure data of its own** |

## 6. Pairwise comparison matrix

Saaty 1–9 scale, reciprocal, defined once in `config.AHP_PAIRWISE_COMPARISON`.
Order: `severity, size, traffic_criticality, recurrence, location_criticality`.

```
                    severity   size   traffic  recurrence  location
severity              1        3       3          5          3
size                 1/3       1       1          3          1
traffic_criticality  1/3       1       1          3          1
recurrence           1/5      1/3     1/3         1         1/3
location_criticality 1/3       1       1          3          1
```

Rationale (full detail in `config.py` comments): severity dominates
because it directly reflects safety/structural risk; size and traffic
criticality are treated as equally important, concrete, measurable
signals; recurrence is the weakest signal (a secondary indicator, not a
direct hazard measure); location criticality is weighted like traffic
criticality but in practice will often fall back to its default since it
needs external GIS data.

## 7. AHP weights (actually computed, principal eigenvector method)

```
lambda_max = 5.041959
CI = (lambda_max - n) / (n - 1) = 0.010490
RI (n=5) = 1.12
CR = CI / RI = 0.009366   →  well under the 0.10 threshold → CONSISTENT
```

| Criterion | Weight |
|---|---|
| severity | 0.443814 |
| size | 0.164508 |
| traffic_criticality | 0.164508 |
| recurrence | 0.062661 |
| location_criticality | 0.164508 |

*(These are computed by `ahp.calculate_ahp_weights()` from the matrix
above — not hand-picked. Re-running `ahp.py` against the same matrix will
reproduce these exact numbers.)*

`ahp.py` **raises `InconsistentMatrixError` at import time** if
`config.AHP_PAIRWISE_COMPARISON` is ever edited into an inconsistent
state (CR > 0.10), so an inconsistent matrix can never silently ship.

## 8. Priority formula

```
priority_raw = Σ (ahp_weight_i × normalized_criterion_i)   over i = 1..5
priority_score = clip(priority_raw × 100, 0, 100)
```

Higher score = higher repair priority. Every criterion's raw value,
normalized value, weight, and contribution is returned in
`priority.breakdown` (see contract below), plus whether it used a
fallback (`is_fallback: true`) because the source data was missing.

## 9. Missing-data behavior (required vs optional)

**Required** (request is rejected with 422 if missing/invalid):
`class_name`, `confidence` (0–1), `bbox` (4 finite, non-negative,
positive-area values).

**Optional, with documented deterministic fallback — never silently
"made up":**

| Field | Fallback when missing | Why this value |
|---|---|---|
| `image_width` / `image_height` | `size_score`/`dimension_score` = 0.5 (neutral midpoint), flagged `"size_estimated": true` | Can't compute a real ratio without image dims; midpoint avoids biasing severity up or down |
| `traffic_criticality` / `road_type` | 0.5 (neutral) | Unknown road class assumed "average," not "highway" or "local" |
| `recurrence_count` | 0.0 (conservative, not neutral) | Absence of recurrence data should not inflate priority |
| `location_criticality` | 0.0 (conservative, not neutral) | No proximity data means we should not assume proximity to critical infrastructure |

Unknown/unmapped `class_name` values use `config.UNKNOWN_DEFECT_TYPE_SEVERITY`
(0.5) and are flagged `"defect_type_unmapped": true` in the severity
breakdown so the class can be added to `config.DEFECT_TYPE_BASE_SEVERITY`.

## 10. Input schema

See `schemas.py` for the full Pydantic v2 definitions. Top-level shape:

```json
{
  "detection": {
    "class_id": 0,
    "class_name": "pothole",
    "confidence": 0.91,
    "bbox": [412.0, 610.0, 587.0, 743.0],
    "image_width": 1920,
    "image_height": 1080
  },
  "context": {
    "latitude": 19.0760,
    "longitude": 72.8777,
    "timestamp": "2026-08-23T09:15:00Z",
    "road_type": "arterial",
    "traffic_criticality": null,
    "recurrence_count": 3,
    "location_criticality": null
  }
}
```

## 11. Output schema

```json
{
  "severity": {
    "score": 0,
    "category": "Low | Medium | High | Critical",
    "breakdown": {
      "defect_type_score": 0,
      "confidence_score": 0,
      "size_score": 0,
      "dimension_score": 0,
      "weighted_contributions": {"defect_type": 0, "confidence": 0, "size": 0, "dimension": 0},
      "data_flags": {"size_estimated": false, "dimension_estimated": false, "defect_type_unmapped": false}
    }
  },
  "priority": {
    "score": 0,
    "breakdown": {
      "severity": {"raw_value": 0, "normalized_value": 0, "weight": 0, "contribution": 0, "is_fallback": false},
      "size": {"...": "same shape"},
      "traffic_criticality": {"...": "same shape"},
      "recurrence": {"...": "same shape"},
      "location_criticality": {"...": "same shape"}
    },
    "ahp": {
      "criteria": ["severity", "size", "traffic_criticality", "recurrence", "location_criticality"],
      "weights": {"severity": 0.4438, "...": "..."},
      "consistency_ratio": 0.009366,
      "is_consistent": true
    }
  }
}
```

## 12. Example request

See `sample_request.json` for the exact JSON, or:

```json
{
  "detection": {
    "class_id": 0,
    "class_name": "pothole",
    "confidence": 0.91,
    "bbox": [412.0, 610.0, 587.0, 743.0],
    "image_width": 1920,
    "image_height": 1080
  },
  "context": {
    "latitude": 19.076,
    "longitude": 72.8777,
    "timestamp": "2026-08-23T09:15:00Z",
    "road_type": "arterial",
    "recurrence_count": 3
  }
}
```

## 13. Example response

**Actually produced by running the code** (see `sample_response.json`),
not hand-written:

```json
{
  "severity": {
    "score": 54.07,
    "category": "High",
    "breakdown": {
      "defect_type_score": 0.95,
      "confidence_score": 0.91,
      "size_score": 0.0748,
      "dimension_score": 0.2463,
      "weighted_contributions": {"defect_type": 0.3325, "confidence": 0.1365, "size": 0.0224, "dimension": 0.0493},
      "data_flags": {"size_estimated": false, "dimension_estimated": false, "defect_type_unmapped": false}
    }
  },
  "priority": {
    "score": 41.33,
    "breakdown": {
      "severity": {"raw_value": 54.07, "normalized_value": 0.5407, "weight": 0.443814, "contribution": 0.23997, "is_fallback": false},
      "size": {"raw_value": 0.011224, "normalized_value": 0.0748, "weight": 0.164508, "contribution": 0.012305, "is_fallback": false},
      "traffic_criticality": {"raw_value": 0.75, "normalized_value": 0.75, "weight": 0.164508, "contribution": 0.123381, "is_fallback": false},
      "recurrence": {"raw_value": 3.0, "normalized_value": 0.6, "weight": 0.062661, "contribution": 0.037596, "is_fallback": false},
      "location_criticality": {"raw_value": null, "normalized_value": 0.0, "weight": 0.164508, "contribution": 0.0, "is_fallback": true}
    },
    "ahp": {
      "criteria": ["severity", "size", "traffic_criticality", "recurrence", "location_criticality"],
      "weights": {"severity": 0.4438, "size": 0.1645, "traffic_criticality": 0.1645, "recurrence": 0.0627, "location_criticality": 0.1645},
      "consistency_ratio": 0.009366,
      "is_consistent": true
    }
  }
}
```

Note `location_criticality.is_fallback: true` — the sample request never
supplied it, so the documented conservative fallback (0.0) was used.

## 14. FastAPI integration

Add a route (adapt path/router to your actual app structure):

```python
from fastapi import APIRouter, HTTPException
from road_intelligence.schemas import AnalyzeRequest, AnalyzeResponse
from road_intelligence import service as road_intelligence_service
from road_intelligence.severity import InvalidDetectionError
from road_intelligence.scoring import InvalidContextError

router = APIRouter()

@router.post("/road-intelligence/analyze", response_model=AnalyzeResponse)
def analyze_defect(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return road_intelligence_service.analyze(request)
    except (InvalidDetectionError, InvalidContextError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
```

The module has **zero database code** — persistence is entirely the
backend's responsibility. Suggested storage for a detections table:

```sql
-- new columns on an existing "detections" table, or a JSONB column
severity_score        NUMERIC(5,2)
severity_category     VARCHAR(16)
severity_breakdown    JSONB
priority_score        NUMERIC(5,2)
priority_breakdown    JSONB   -- includes the "ahp" sub-object
```

`response.severity.model_dump()` / `response.priority.model_dump()`
(Pydantic v2) serialize directly to JSON-compatible dicts suitable for a
`JSONB` column — no extra transformation needed.

## 15. Package layout

```
road_intelligence/
├── __init__.py
├── config.py     # every weight, threshold, mapping — single source of truth
├── schemas.py    # Pydantic v2 input/output contract (API boundary)
├── severity.py   # pure-Python severity core (no pydantic dependency)
├── ahp.py        # pure-Python AHP eigenvector/consistency core
├── scoring.py    # pure-Python priority combination core
├── service.py    # FastAPI-facing adapter: pydantic <-> pure-Python core
└── tests/
    ├── test_severity.py   (30 tests)
    └── test_ahp.py        (21 tests)
```

`severity.py`, `ahp.py`, and `scoring.py` have **no pydantic/FastAPI
dependency** by design — they're independently unit-testable and reusable
(batch scoring jobs, notebooks) without a web framework in the loop.
`service.py` is the only file that touches both worlds.

## 16. Adapt before production use

1. **Replace `config.DEFECT_TYPE_BASE_SEVERITY` keys** with the real YOLO
   model's exact class names (or add a `class_id -> class_name` lookup if
   the real model only emits integer ids).
2. **Confirm `bbox` format.** This module assumes `[x_min, y_min, x_max,
   y_max]` pixel coordinates (standard YOLO post-NMS output). If the real
   pipeline emits `[x, y, w, h]` or normalized `[0,1]` coordinates,
   convert in `service._to_detection_data()` before calling
   `severity.estimate_severity()` — everything downstream only needs
   `bbox_area_ratio` to end up correctly in `[0, 1]`.
3. **Review the AHP pairwise matrix and severity weights** with whoever
   owns repair-priority policy — they are a defensible, internally
   consistent starting point (CR = 0.0094), not a validated/calibrated
   model, since no historical repair-outcome data was available to
   calibrate against.
4. **Confirm `config.ROAD_TYPE_CRITICALITY` keys** (`local`, `collector`,
   `arterial`, `highway`) match whatever road classification the
   backend/GIS system actually uses, or wire `traffic_criticality`
   directly as a pre-normalized float instead.
5. **`location_criticality`** requires external GIS/infrastructure data
   this module doesn't have. Until the backend supplies it, every
   detection will use the conservative fallback (0.0) and be flagged
   `is_fallback: true` — expected, not a bug.
