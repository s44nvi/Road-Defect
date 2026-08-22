# Road Health Intelligence System

Smart road-defect detection and maintenance prioritization for municipal teams.

## What this repository contains

This repository is organized as a modular monorepo for the SIH26_90 Purple Hand Gang solution:

```text
apps/
	web/                 Next.js municipal dashboard
services/
	api/                 FastAPI application and public API boundary
	worker/              Async detection, fusion, scoring, and verification jobs
packages/
	contracts/           Shared event and API contract definitions
infra/
	docker/              Local infrastructure and deployment notes
docs/
	architecture.md      System design and data flows
```

## Product flow

```text
Capture -> Detect -> Locate -> Fuse -> Consolidate -> Score -> Verify
																												 |
												 Post-repair validation <- Repair <- Schedule
```

The system treats each observation as evidence. Multiple observations are merged into one persistent defect, then an explainable priority score helps officers decide which verified defects should be repaired first.

## MVP boundaries

- Camera, GPS, and accelerometer observations are accepted through the API.
- Detection and sensor processing run as background jobs so uploads remain responsive.
- PostgreSQL/PostGIS is the source of truth for defects, observations, road segments, crews, and repairs.
- Officer verification is required before a defect can be scheduled.
- Crew data and repair history may be seeded as clearly labelled synthetic demo data.
- Exact pothole depth in centimetres is not claimed; severity is an estimated class and score.

## Planned stack

- **Web:** Next.js, TypeScript, Mapbox or Leaflet
- **API:** FastAPI, Pydantic, SQLAlchemy, PostgreSQL/PostGIS
- **Processing:** Python, YOLO model adapter, OpenCV, Redis-backed job queue
- **Scheduling:** OR-Tools
- **Operations:** Docker Compose locally; object storage for evidence clips and images

See [docs/architecture.md](docs/architecture.md) for ownership boundaries, domain entities, processing stages, and the implementation order.

## Local development

The initial commit establishes the architecture and service contracts. Each service directory contains its implementation entry point and local setup notes. Copy `.env.example` to `.env` when service implementation begins.