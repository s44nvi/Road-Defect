"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { Map as MaplibreMap, Marker, GeoJSONSource, MapLayerMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { createRoot, type Root } from "react-dom/client";
import { DefectMarker } from "./defect-marker";
import { MUMBAI_CENTER, OSM_STYLE } from "./osm-style";
import { HEALTH_BAND_HEX, HEALTH_BAND_LABEL, healthBandForScore } from "@/lib/road-health";
import type { DefectResponse, RoadHealthSegment } from "@/lib/api";

const ROAD_HEALTH_SOURCE_ID = "road-health-source";
const ROAD_HEALTH_HALO_LAYER_ID = "road-health-halo";
const ROAD_HEALTH_LINE_LAYER_ID = "road-health-line";
const ROAD_HEALTH_SELECTED_LAYER_ID = "road-health-line-selected";
const NO_SELECTION_SENTINEL = "__none__";

// Plain-string HTML (not a React root) for the transient hover tooltip —
// MapLibre shows/hides/repositions a Popup on every mousemove, so a
// template string is far cheaper here than mounting/unmounting React on
// every frame. Tailwind's compiled stylesheet already covers the whole
// document, so these utility classes render correctly inside it.
function hoverTooltipHtml(segment: RoadHealthSegment): string {
  const band = healthBandForScore(segment.health_score);
  const colorClass =
    band === "healthy" ? "text-primary" : band === "critical" ? "text-error" : "text-[#f59e0b]";
  return `
    <div class="min-w-[180px] text-sm">
      <p class="font-semibold text-on-surface">${segment.road_name}</p>
      <p class="mt-1 font-bold ${colorClass}">${segment.health_score.toFixed(1)} / 10 — ${HEALTH_BAND_LABEL[band]}</p>
      <div class="mt-2 flex items-center justify-between text-xs text-on-surface-variant">
        <span>${segment.total_issues} total</span>
        <span>${segment.open_issues} open</span>
        <span>${segment.resolved_issues} resolved</span>
      </div>
      <p class="mt-1 text-xs text-error">${segment.critical_issues} critical</p>
    </div>
  `;
}

function segmentsToGeoJSON(segments: RoadHealthSegment[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: segments.map((segment) => ({
      type: "Feature",
      geometry: segment.geometry,
      properties: { road_segment_id: segment.road_segment_id, health_category: segment.health_category },
    })),
  };
}

export function DefectMap({
  defects,
  selectedId,
  onSelect,
  roadSegments,
  selectedSegmentId,
  onSelectSegment,
}: {
  defects: DefectResponse[];
  selectedId: number | null;
  onSelect: (defect: DefectResponse | null) => void;
  /** Real road-health segments only — pass [] (the default until a backend
   * endpoint exists) rather than any fabricated geometry. */
  roadSegments?: RoadHealthSegment[];
  selectedSegmentId?: string | null;
  onSelectSegment?: (segment: RoadHealthSegment | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const markersRef = useRef<Map<number, { marker: Marker; root: Root }>>(new Map());
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const roadSegmentsRef = useRef<RoadHealthSegment[]>(roadSegments ?? []);
  roadSegmentsRef.current = roadSegments ?? [];
  const onSelectSegmentRef = useRef(onSelectSegment);
  onSelectSegmentRef.current = onSelectSegment;
  const hoverPopupRef = useRef<maplibregl.Popup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: MUMBAI_CENTER,
      zoom: 11,
      // attributionControl defaults on — kept implicit rather than passed,
      // since MapLibre's type only accepts a config object or `false` here.
      // Do not disable it: the OSM raster tiles require attribution.
    });
    // top-left is the one corner not already used by the severity legend
    // (top-right) or the health-summary / selected-defect overlay cards
    // (bottom), so the zoom control never collides with them.
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    mapRef.current = map;
    hoverPopupRef.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      maxWidth: "260px",
      offset: 8,
    });

    return () => {
      markersRef.current.forEach(({ marker, root }) => {
        root.unmount();
        marker.remove();
      });
      markersRef.current.clear();
      hoverPopupRef.current?.remove();
      hoverPopupRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const currentIds = new Set(defects.map((defect) => defect.defect_id));

    markersRef.current.forEach(({ marker, root }, id) => {
      if (!currentIds.has(id)) {
        root.unmount();
        marker.remove();
        markersRef.current.delete(id);
      }
    });

    defects.forEach((defect) => {
      const selected = defect.defect_id === selectedId;
      const existing = markersRef.current.get(defect.defect_id);

      if (existing) {
        existing.root.render(
          <DefectMarker
            defectType={defect.defect_type}
            severity={defect.defect_severity}
            selected={selected}
          />,
        );
        existing.marker.setLngLat([defect.longitude, defect.latitude]);
        return;
      }

      const el = document.createElement("div");
      el.style.cursor = "pointer";
      el.addEventListener("click", (event) => {
        event.stopPropagation();
        onSelectRef.current(defect);
      });

      const root = createRoot(el);
      root.render(
        <DefectMarker
          defectType={defect.defect_type}
          severity={defect.defect_severity}
          selected={selected}
        />,
      );

      const marker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([defect.longitude, defect.latitude])
        .addTo(map);

      markersRef.current.set(defect.defect_id, { marker, root });
    });
  }, [defects, selectedId]);

  // Road-health line layer — added lazily once the style has finished
  // loading, and only actually draws anything once `roadSegments` is
  // non-empty (i.e. once a real backend response has data in it).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    function syncSource() {
      const data = segmentsToGeoJSON(roadSegmentsRef.current);
      const existingSource = map!.getSource(ROAD_HEALTH_SOURCE_ID) as GeoJSONSource | undefined;
      if (existingSource) {
        existingSource.setData(data);
        return;
      }

      map!.addSource(ROAD_HEALTH_SOURCE_ID, { type: "geojson", data });
      map!.addLayer({
        id: ROAD_HEALTH_HALO_LAYER_ID,
        type: "line",
        source: ROAD_HEALTH_SOURCE_ID,
        filter: ["==", ["get", "road_segment_id"], NO_SELECTION_SENTINEL],
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#1b1c1a", "line-width": 9, "line-opacity": 0.25 },
      });
      map!.addLayer({
        id: ROAD_HEALTH_LINE_LAYER_ID,
        type: "line",
        source: ROAD_HEALTH_SOURCE_ID,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": [
            "match",
            ["get", "health_category"],
            "healthy",
            HEALTH_BAND_HEX.healthy,
            "needs_attention",
            HEALTH_BAND_HEX.needs_attention,
            "critical",
            HEALTH_BAND_HEX.critical,
            "#9ca3af",
          ],
          "line-width": 4,
        },
      });

      // Registered only once, right after the layer is created — doing this
      // any earlier risks MapLibre querying a layer that doesn't exist yet.
      map!.on("click", ROAD_HEALTH_LINE_LAYER_ID, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        const id = feature?.properties?.road_segment_id;
        const segment = roadSegmentsRef.current.find((s) => s.road_segment_id === id) ?? null;
        onSelectSegmentRef.current?.(segment);
      });
      map!.on("mouseenter", ROAD_HEALTH_LINE_LAYER_ID, () => {
        map!.getCanvas().style.cursor = "pointer";
      });
      map!.on("mousemove", ROAD_HEALTH_LINE_LAYER_ID, (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        const id = feature?.properties?.road_segment_id;
        const segment = roadSegmentsRef.current.find((s) => s.road_segment_id === id);
        if (segment) {
          hoverPopupRef.current?.setLngLat(e.lngLat).setHTML(hoverTooltipHtml(segment)).addTo(map!);
        }
      });
      map!.on("mouseleave", ROAD_HEALTH_LINE_LAYER_ID, () => {
        map!.getCanvas().style.cursor = "";
        hoverPopupRef.current?.remove();
      });
    }

    if (map.isStyleLoaded()) {
      syncSource();
    } else {
      map.once("load", syncSource);
    }
  }, [roadSegments]);

  // Selection halo filter — kept in its own effect so changing the
  // selected segment never touches the source data.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer(ROAD_HEALTH_HALO_LAYER_ID)) return;
    map.setFilter(ROAD_HEALTH_HALO_LAYER_ID, [
      "==",
      ["get", "road_segment_id"],
      selectedSegmentId ?? NO_SELECTION_SENTINEL,
    ]);
  }, [selectedSegmentId]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      onClick={() => onSelectRef.current(null)}
    />
  );
}
