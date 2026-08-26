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
