"use client";

import { useEffect, useRef, useState } from "react";
import type { HawkerDetectionItem } from "@/lib/api";

const BOX_COLORS = ["#ba1a1a", "#006948", "#f59e0b", "#1d4ed8", "#9333ea"];

// The API returns bbox coordinates in the *original* uploaded image's
// pixel dimensions (see lib/api.ts's HawkerDetection). The <img> here is
// rendered at `width: 100%; height: auto`, which scales both axes by the
// same ratio and never letterboxes — so naturalWidth/naturalHeight vs.
// clientWidth/clientHeight gives an exact, reliable scale factor. Using
// object-fit/contain instead would break this, since the rendered image
// content could then be smaller than the element's box.
export function BoundingBoxOverlay({
  imageUrl,
  detections,
}: {
  imageUrl: string;
  detections: HawkerDetectionItem[];
}) {
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const [renderSize, setRenderSize] = useState<{ width: number; height: number } | null>(null);

  function syncSizes() {
    const img = imgRef.current;
    if (!img) return;
    setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
    setRenderSize({ width: img.clientWidth, height: img.clientHeight });
  }

  useEffect(() => {
    // The image may already be loaded (cached) by the time this effect
    // runs, in which case onLoad never fires — sync immediately too.
    syncSizes();

    function handleResize() {
      if (imgRef.current) {
        setRenderSize({ width: imgRef.current.clientWidth, height: imgRef.current.clientHeight });
      }
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageUrl]);

  const scaleX = naturalSize && renderSize && naturalSize.width > 0 ? renderSize.width / naturalSize.width : null;
  const scaleY = naturalSize && renderSize && naturalSize.height > 0 ? renderSize.height / naturalSize.height : null;

  return (
    <div className="relative w-full max-w-xl">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        ref={imgRef}
        src={imageUrl}
        alt="Uploaded for hawker/encroachment detection"
        className="block w-full rounded-lg border border-border-subtle"
        onLoad={syncSizes}
      />
      {scaleX !== null &&
        scaleY !== null &&
        detections.map((detection, index) => {
          const [xMin, yMin, xMax, yMax] = detection.bbox;
          const color = BOX_COLORS[index % BOX_COLORS.length];
          return (
            <div
              key={index}
              className="pointer-events-none absolute border-2"
              style={{
                left: xMin * scaleX,
                top: yMin * scaleY,
                width: Math.max(0, (xMax - xMin) * scaleX),
                height: Math.max(0, (yMax - yMin) * scaleY),
                borderColor: color,
              }}
            >
              <span
                className="absolute -top-6 left-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-semibold text-white"
                style={{ backgroundColor: color }}
              >
                {/* The three underlying vendor classes are intentionally
                    never shown — see components/report/hawker-analysis.tsx. */}
                Vendor · {(detection.confidence * 100).toFixed(0)}%
              </span>
            </div>
          );
        })}
    </div>
  );
}
