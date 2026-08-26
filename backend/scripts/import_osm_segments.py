"""
import_osm_segments.py
======================
Imports REAL road geometry from OpenStreetMap and replaces the bundled
approximate development corridors.

    python -m backend.scripts.import_osm_segments \
        --road "Western Express Highway" \
        --bbox 18.89,72.77,19.28,73.03

    python -m backend.scripts.import_osm_segments \
        --road "Eastern Express Highway" --bbox 18.89,72.77,19.28,73.03 \
        --segment-prefix OSM --replace-dev-segments

    # Or, where the Overpass endpoint is unreachable (network policy) but a
    # pre-exported extract (e.g. from overpass-turbo) is available on disk:
    python -m backend.scripts.import_osm_segments \
        --road "Eastern Express Highway" \
        --geojson-file eastern_express_highway.geojson \
        --exclude-name "Eastern Express Turnpike" \
        --segment-prefix OSM --replace-dev-segments

Why this script exists
----------------------
The bundled `mumbai_corridors.geojson` is APPROXIMATE, HAND-AUTHORED
DEVELOPMENT GEOMETRY (see `backend/app/road_health/data/README.md`). It was not
possible to fetch real OSM geometry live at implementation time because the
build environment's network policy blocks every OpenStreetMap endpoint
(`overpass-api.de`, `overpass.kumi.systems`, `nominatim.openstreetmap.org` and
`router.project-osrm.org` all return `CONNECT tunnel failed, 403`).

**The live Overpass path (`--bbox`) has therefore never been executed against
a real endpoint from this environment.** `--geojson-file` was added so a
pre-exported overpass-turbo GeoJSON extract can be imported instead, without
requiring live network access; it uses only the standard library, so no new
dependency is introduced either way.

Segments it creates are stamped `geometry_source = 'osm_overpass'`, so real and
approximate geometry are always distinguishable in the database. Afterwards run
`python -m backend.scripts.backfill_defect_segments --reassign-all` to re-snap
defects onto the new geometry.

OSM data is (c) OpenStreetMap contributors, licensed under the ODbL
(https://www.openstreetmap.org/copyright). Carry that attribution into anything
you publish from it.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

from backend.app.database import SessionLocal
from backend.app.models import RoadSegment
from backend.app.road_health.config import (
    GEOMETRY_SOURCE_DEV,
    GEOMETRY_SOURCE_OSM,
    TARGET_SEGMENT_LENGTH_KM,
)
from backend.app.road_health.geo import (
    haversine_km,
    linestring,
    linestring_length_km,
    split_into_segments,
)

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"

# Ways whose `name` matches, restricted to actual roads, returned with their
# full coordinate geometry.
QUERY_TEMPLATE = """
[out:json][timeout:{timeout}];
way["name"="{road}"]["highway"]({bbox});
out geom;
"""


def fetch_ways(road: str, bbox: str, endpoint: str, timeout: int) -> list[list[list[float]]]:
    """Query Overpass and return each matching way as a [lon, lat] polyline."""
    query = QUERY_TEMPLATE.format(road=road, bbox=bbox, timeout=timeout)

    request = urllib.request.Request(
        endpoint,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": "Road-Defect road-health importer"},
    )

    with urllib.request.urlopen(request, timeout=timeout + 30) as response:
        payload = json.load(response)

    ways = []

    for element in payload.get("elements", []):
        geometry = element.get("geometry") or []

        if len(geometry) >= 2:
            ways.append([[point["lon"], point["lat"]] for point in geometry])

    return ways


def fetch_ways_from_file(
    path: str,
    exclude_names: list[str] | None = None,
) -> list[list[list[float]]]:
    """
    Load ways from a local GeoJSON FeatureCollection instead of querying
    Overpass live -- for environments where the Overpass endpoint is
    unreachable (network policy) but a pre-exported extract (e.g. from
    overpass-turbo) is available on disk.

    A single Overpass "name" query commonly returns more than one real road
    that happens to share the bounding box (a parallel service road, a
    differently-numbered link road). Rather than silently guessing which
    features belong to the intended corridor, this only ever DROPS a feature
    when its exact `name` property is explicitly listed in `exclude_names` --
    every other LineString feature in the file is kept as-is. Only real
    coordinates from the file are used; nothing is fabricated or altered.
    """
    with open(path) as handle:
        collection = json.load(handle)

    if collection.get("type") != "FeatureCollection":
        raise SystemExit(f"{path}: not a GeoJSON FeatureCollection")

    excluded = set(exclude_names or [])
    ways = []

    for feature in collection.get("features", []):
        if feature.get("type") != "Feature":
            continue

        name = (feature.get("properties") or {}).get("name")

        if name in excluded:
            continue

        geometry = feature.get("geometry") or {}

        if geometry.get("type") != "LineString":
            continue

        coordinates = geometry.get("coordinates") or []

        if len(coordinates) >= 2:
            ways.append([[float(lon), float(lat)] for lon, lat in coordinates])

    return ways


def _grow_cluster(
    seed: list[list[float]],
    remaining: list[list[list[float]]],
    gap_tolerance_km: float,
) -> list[list[float]]:
    """
    Grow one connected corridor from a seed way, consuming matching ways out of
    `remaining` (in place) as it finds them.

    Unlike a single forward-only walk from the tail, this searches EVERY
    remaining way against BOTH ends of the growing corridor on each pass, in
    either orientation, and always attaches whichever candidate is closest
    overall. That makes the result independent of the arbitrary order Overpass
    returns ways in and independent of which way happened to seed the cluster:
    a way is only ever left unattached because nothing is within
    `gap_tolerance_km` of either end, never because it appeared "too early" or
    "too late" in the input list.
    """
    corridor = list(seed)

    while remaining:
        head_lon, head_lat = corridor[0]
        tail_lon, tail_lat = corridor[-1]

        best_index = None
        best_distance = float("inf")
        best_end = None  # "head" or "tail"
        best_flipped = False

        for index, way in enumerate(remaining):
            way_start_lon, way_start_lat = way[0]
            way_end_lon, way_end_lat = way[-1]

            candidates = (
                ("tail", False, tail_lat, tail_lon, way_start_lat, way_start_lon),
                ("tail", True, tail_lat, tail_lon, way_end_lat, way_end_lon),
                ("head", False, head_lat, head_lon, way_end_lat, way_end_lon),
                ("head", True, head_lat, head_lon, way_start_lat, way_start_lon),
            )

            for end, flipped, lat1, lon1, lat2, lon2 in candidates:
                distance = haversine_km(lat1, lon1, lat2, lon2)

                if distance < best_distance:
                    best_index, best_distance = index, distance
                    best_end, best_flipped = end, flipped

        if best_index is None or best_distance > gap_tolerance_km:
            break

        way = remaining.pop(best_index)

        if best_end == "tail":
            if best_flipped:
                way = list(reversed(way))
            corridor.extend(way[1:])
        else:
            if best_flipped:
                way = list(reversed(way))
            corridor = way[:-1] + corridor

    return corridor


def _build_clusters(
    ways: list[list[list[float]]],
    gap_tolerance_km: float,
) -> list[list[list[float]]]:
    """
    Group ways into every connected cluster (shared by `stitch()` and
    `stitch_all_clusters()`). See `stitch()` for what "connected" means.
    """
    if not ways:
        return []

    remaining = [list(way) for way in ways]
    clusters: list[list[list[float]]] = []

    while remaining:
        seed = remaining.pop(0)
        clusters.append(_grow_cluster(seed, remaining, gap_tolerance_km))

    return clusters


def stitch(ways: list[list[list[float]]], gap_tolerance_km: float = 0.05) -> list[list[float]]:
    """
    Join OSM ways into one corridor polyline: the single longest connected
    cluster (see `stitch_all_clusters()` to keep every real cluster instead).

    Overpass returns a road as many disjoint ways, in NO guaranteed order --
    not necessarily geographic, and any given way may be stored in either
    direction. This builds every connected cluster of ways (extending each
    cluster from both ends, trying both orientations of every remaining way on
    every pass) and returns the longest one, so:

      * arbitrary way ordering never causes real road geometry to be dropped --
        every way ends up in whichever cluster it geographically belongs to,
        regardless of where it appeared in the input list;
      * a reversed way is joined correctly either way;
      * the corridor grows from both its head and its tail, not just the tail;
      * ways farther apart than `gap_tolerance_km` are never joined -- that is
        a genuine break in the road (a real gap), not a split-way artifact, so
        they end up in a separate cluster instead of being bridged.

    Only real OSM coordinates are ever used; nothing here fabricates or
    straightens geometry.
    """
    clusters = _build_clusters(ways, gap_tolerance_km)

    if not clusters:
        return []

    return max(clusters, key=linestring_length_km)


def stitch_all_clusters(
    ways: list[list[list[float]]],
    gap_tolerance_km: float = 0.05,
    min_cluster_km: float = 1.0,
) -> list[list[list[float]]]:
    """
    Like `stitch()`, but keeps every connected cluster at or above
    `min_cluster_km` instead of only the single longest one.

    A divided highway (or any road whose OSM `name` tag isn't applied to every
    intermediate way) commonly fragments into several real, genuinely
    disconnected clusters scattered along its length -- not just one "main"
    corridor and noise. Discarding all but the longest throws away real,
    unfabricated road geometry. This keeps every cluster long enough to be a
    meaningful road stretch (default 1.0 km) and drops only clusters below
    that -- almost always short slip-road/ramp fragments -- while never
    joining, interpolating, or altering a single coordinate.

    Returned clusters are sorted longest first, for deterministic segment
    numbering.
    """
    clusters = _build_clusters(ways, gap_tolerance_km)

    kept = [c for c in clusters if linestring_length_km(c) >= min_cluster_km]
    kept.sort(key=linestring_length_km, reverse=True)

    return kept


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--road", required=True, help="Exact OSM `name` tag of the road.")
    parser.add_argument(
        "--bbox",
        help="Overpass bbox as 'south,west,north,east' (e.g. 18.89,72.77,19.28,73.03). "
             "Required unless --geojson-file is given.",
    )
    parser.add_argument(
        "--geojson-file",
        help="Load ways from a local GeoJSON FeatureCollection (e.g. an "
             "overpass-turbo export) instead of querying Overpass live. Use "
             "this where the Overpass endpoint is unreachable. --bbox is "
             "ignored when this is set.",
    )
    parser.add_argument(
        "--exclude-name",
        action="append",
        default=[],
        metavar="NAME",
        help="With --geojson-file: drop every feature whose exact `name` "
             "property equals NAME (repeatable). Use this to remove a "
             "different real road that happens to share the file -- e.g. a "
             "parallel service road returned by the same broad query.",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--segment-prefix",
        default="OSM",
        help="Prefix for generated segment ids (default OSM -> OSM-001).",
    )
    parser.add_argument(
        "--target-length-km",
        type=float,
        default=TARGET_SEGMENT_LENGTH_KM,
    )
    parser.add_argument(
        "--min-cluster-km",
        type=float,
        default=1.0,
        help="Keep every real connected cluster of ways at or above this "
             "length (default 1.0 km) as its own road segment; shorter "
             "clusters (almost always slip-road/ramp fragments) are dropped. "
             "Nothing is joined or fabricated across the clusters that "
             "remain separate.",
    )
    parser.add_argument(
        "--replace-dev-segments",
        action="store_true",
        help="Delete this road's approximate development segments "
             f"(geometry_source='{GEOMETRY_SOURCE_DEV}') after importing. "
             "Refuses to delete a segment that still has defects attached.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.geojson_file:
        ways = fetch_ways_from_file(args.geojson_file, exclude_names=args.exclude_name)
        source_desc = f"local file {args.geojson_file!r}"
    else:
        if not args.bbox:
            raise SystemExit("--bbox is required unless --geojson-file is given.")
        ways = fetch_ways(args.road, args.bbox, args.endpoint, args.timeout)
        source_desc = f"Overpass ({args.endpoint})"

    if not ways:
        raise SystemExit(f"No usable ways found for {args.road!r} from {source_desc}.")

    all_clusters = _build_clusters(ways, gap_tolerance_km=0.05)
    clusters = [c for c in all_clusters if linestring_length_km(c) >= args.min_cluster_km]
    clusters.sort(key=linestring_length_km, reverse=True)

    if not clusters:
        raise SystemExit(
            f"No cluster at or above --min-cluster-km={args.min_cluster_km} "
            f"was found for {args.road!r}."
        )

    dropped = len(all_clusters) - len(clusters)
    total_km = sum(linestring_length_km(c) for c in clusters)

    print(f"Loaded {len(ways)} way(s) from {source_desc}")
    print(
        f"Found {len(all_clusters)} connected cluster(s); kept {len(clusters)} "
        f">= {args.min_cluster_km} km (dropped {dropped}), total {total_km:.2f} km"
    )
    for i, c in enumerate(clusters):
        print(f"  cluster {i}: {linestring_length_km(c):.3f} km")

    # Each retained cluster is split independently: split_into_segments()
    # already returns the cluster unchanged as a single piece when its own
    # length doesn't exceed the target, so this preserves the existing
    # single-corridor splitting behaviour without any extra branching.
    pieces = [
        piece
        for cluster in clusters
        for piece in split_into_segments(cluster, args.target_length_km)
    ]

    print(f"Split into {len(pieces)} segment(s) of ~{args.target_length_km} km total")

    db = SessionLocal()

    try:
        for index, piece in enumerate(pieces, start=1):
            segment_id = f"{args.segment_prefix}-{index:03d}"

            segment = (
                db.query(RoadSegment)
                .filter(RoadSegment.segment_id == segment_id)
                .first()
            )

            if segment is None:
                segment = RoadSegment(segment_id=segment_id)
                db.add(segment)

            segment.road_name = args.road
            segment.segment_label = f"{args.road} - Segment {index}"
            segment.geometry = linestring(piece)
            segment.length_km = round(linestring_length_km(piece), 3)
            segment.geometry_source = GEOMETRY_SOURCE_OSM

            print(f"  {segment_id}: {segment.length_km} km")

        if args.replace_dev_segments:
            stale = (
                db.query(RoadSegment)
                .filter(
                    RoadSegment.road_name == args.road,
                    RoadSegment.geometry_source == GEOMETRY_SOURCE_DEV,
                )
                .all()
            )

            for segment in stale:
                if segment.defects:
                    print(
                        f"  keeping {segment.segment_id}: still has "
                        f"{len(segment.defects)} defect(s) attached. Run "
                        "backfill_defect_segments --reassign-all, then re-run "
                        "with --replace-dev-segments."
                    )
                    continue

                print(f"  removing development segment {segment.segment_id}")
                db.delete(segment)

        if args.dry_run:
            db.rollback()
            print("DRY RUN -- nothing written.")
        else:
            db.commit()
            print("Imported. Now run: python -m backend.scripts.backfill_defect_segments "
                  "--reassign-all")

    finally:
        db.close()


if __name__ == "__main__":
    main()
