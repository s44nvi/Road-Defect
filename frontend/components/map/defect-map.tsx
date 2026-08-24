"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type { Map as MaplibreMap, Marker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { createRoot, type Root } from "react-dom/client";
import { DefectMarker } from "./defect-marker";
import { MUMBAI_CENTER, OSM_STYLE } from "./osm-style";
import type { DefectResponse } from "@/lib/api";

export function DefectMap({
  defects,
  selectedId,
  onSelect,
}: {
  defects: DefectResponse[];
  selectedId: number | null;
  onSelect: (defect: DefectResponse | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const markersRef = useRef<Map<number, { marker: Marker; root: Root }>>(new Map());
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

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

    return () => {
      markersRef.current.forEach(({ marker, root }) => {
        root.unmount();
        marker.remove();
      });
      markersRef.current.clear();
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

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      onClick={() => onSelectRef.current(null)}
    />
  );
}
