# Road Health geometry data

## What is in here

`mumbai_corridors.geojson` — a GeoJSON `FeatureCollection` of five Mumbai road
corridors as `LineString` features. `backend/scripts/seed_road_health_dev_data.py`
reads this file, cuts each corridor into ~15 km segments along its own geometry
(`road_health.geo.split_into_segments`), and inserts the results into
`road_segments`.

| Corridor | Extent | Approx. length | Segments |
|---|---|---|---|
| Western Express Highway | Bandra (Kalanagar) → Dahisar Check Naka | 21.1 km | 2 |
| Eastern Express Highway | Sion → Thane (Teen Hath Naka) | 22.6 km | 2 |
| Lal Bahadur Shastri Marg | Sion → Mulund | 17.5 km | 1 |
| Sion-Panvel Highway | Sion → Nerul | 20.5 km | 2 |
| Swami Vivekanand Road | Bandra West → Dahisar | 21.9 km | 2 |

## Where this geometry came from — read this before trusting it

**This is approximate development/test geometry. It is not surveyed data and it
is not OpenStreetMap data.**

The polylines were hand-authored to follow the general alignment of each
corridor. They are realistic enough to draw on a map, to segment by real
chainage, and to snap defects against — which is all the Road Health feature
needs in development — but individual vertices are **not** accurate to the
actual carriageway. Do not use them for navigation, asset management, or
anything where being off by tens of metres matters.

Every row this data produces is stamped `road_segments.geometry_source =
'dev_approximate_v1'`, and every feature carries a `provenance` property saying
the same thing, so fabricated geometry can never be mistaken for real geometry
downstream.

Real OSM geometry was not fetched at implementation time because the build
environment's network policy blocks every OpenStreetMap endpoint
(`overpass-api.de`, `overpass.kumi.systems`, `nominatim.openstreetmap.org`,
`router.project-osrm.org` all return `CONNECT tunnel failed, 403`).

## Replacing it with real road geometry

`backend/scripts/import_osm_segments.py` queries the Overpass API for the real
OSM ways of a named road, stitches them into a corridor polyline, applies the
same segmentation, and writes segments stamped `geometry_source = 'osm_overpass'`.
Run it from a machine with OpenStreetMap access:

```bash
python -m backend.scripts.import_osm_segments \
    --road "Western Express Highway" \
    --bbox 18.89,72.77,19.28,73.03 \
    --replace-dev-segments
```

No application code changes are needed — the API, scoring, and assignment logic
read whatever geometry is in the table. Defects are re-snapped automatically by
`backend/scripts/backfill_defect_segments.py` afterwards.

OSM data is © OpenStreetMap contributors, licensed under the
[ODbL](https://www.openstreetmap.org/copyright); if you import it, carry that
attribution into anything you publish.

## Real MCGM demo data

For the demo, 10 REAL MCGM (Mumbai civic) road-works records were supplied as
CSVs (not committed to the repo — they live outside `backend/`, e.g.
`~/Downloads/demo_roads.csv`) and are imported by three repeatable, idempotent
scripts. Every row is stamped `geometry_source = 'mcgm_demo_csv_v1'`
(`road_health/config.py`), distinct from `dev_approximate_v1`/`osm_overpass`.

| CSV | Script | Table | Rows |
|---|---|---|---|
| `demo_roads.csv` | `python -m backend.scripts.import_demo_roads [--csv PATH] [--dry-run]` | `road_segments` (upsert by `segment_id = f"MCGM-{csv_id}"`) | 10 |
| `demo_manholes.csv` | `python backend/scripts/import_demo_manholes.py` | `manholes` (upsert by `object_id`) | 179 |
| `demo_encroachments.csv` | `python backend/scripts/import_demo_encroachments.py` | `encroachments` (upsert by `object_id`) | 56 |

Run in that order (manholes/encroachments associate to the 10 MCGM roads
already in `road_segments`, and refuse to run if that count isn't exactly 10).
Each script upserts by its own stable external id, so re-running any of them
updates the same rows rather than creating duplicates.

**Geometry.** 7 of the 10 roads are a plain WKT `LINESTRING`; 3
(`18th Road`, `15thRoad`, `13th Road,Khar(W)`) are `MULTILINESTRING`, each with
two parts. All three are stored and served as genuine GeoJSON
`MultiLineString` (`road_health/geo.parse_geometry_parts` /
`multi_linestring`) — parts are never merged, reordered, or bridged with an
invented connecting line, even where the gap between two parts is only a few
metres (18th Road, 15thRoad). `13th Road,Khar(W)`'s two parts are ~774 m
apart — a genuine break in the source data, not a digitization artifact —
and are preserved exactly that way. `road_health/assignment.py` and
`road_health/service.py` handle both `LineString` and `MultiLineString`
uniformly via `geo.parse_geometry_parts`/`geo.point_to_geometry_distance_km`,
so nothing downstream (Road Health scoring, defect-to-segment snapping,
`GET /road-health/segments/{id}`) special-cases either shape.

**Length.** `road_segments.length_km` is always computed from the actual
geometry (`geo.total_length_km` — the sum of each part's own haversine
length, never a distance across a genuine multi-part gap). The CSV's own
`length_of_road_m` is preserved separately as `source_length_m`; the two
numbers legitimately disagree for several roads and neither is forced to
match the other.

**Manholes/encroachments vs Road Health — the architectural line.** Both are
context/infrastructure, not defects: `backend/app/assets/` (models `Manhole`,
`Encroachment` in `app/models.py`; router `app/assets/router.py`) is a
separate module from `road_health/`, and `road_health/scoring.py` only ever
reads `Defect` rows — it has no import of, or reference to, `Manhole` or
`Encroachment`. Neither table's rows ever change `health_score`,
`total_issues`, or any severity/priority field. They are exposed read-only via:

```
GET /assets/manholes[?segment_id=MCGM-2353]
GET /assets/encroachments[?segment_id=MCGM-2353]
GET /road-health/segments/{segment_id}/assets   -> {"manhole_count", "encroachment_count", "manholes": [...], "encroachments": [...]}
```

**Association.** Each manhole/encroachment is snapped to the nearest of the
10 MCGM road segments by real point-to-polyline distance (handling
`MultiLineString` segments the same way `road_health/assignment.py` does),
within a 50 m threshold; beyond that it is left unassociated
(`road_segment_id = NULL`) rather than guessed. In this dataset all 179
manholes and all 56 encroachments fell within 50 m of their nearest MCGM
road.
