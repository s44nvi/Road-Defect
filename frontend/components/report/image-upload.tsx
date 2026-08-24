"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { CameraIcon, TrashIcon } from "@/components/icons";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const ACCEPTED_LABEL = "JPEG, PNG or WebP";
const MAX_SIZE_BYTES = 8 * 1024 * 1024;

export interface ImageUploadValue {
  file: File;
  previewUrl: string;
}

// NOTE: backend/app/schemas.py::ReportCreate has no image/file field, and
// there is no upload endpoint anywhere in backend/app/main.py. The photo
// is kept entirely client-side (an object URL preview) so the upload UX is
// real and usable, but it is never sent anywhere — see lib/api.ts's
// submitReport(), which only transmits the four fields the backend
// actually accepts. This is intentional, not a bug: swap in a real upload
// call here once the backend exposes one.
export function ImageUpload({
  value,
  onChange,
}: {
  value: ImageUploadValue | null;
  onChange: (value: ImageUploadValue | null) => void;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const valueRef = useRef(value);
  valueRef.current = value;
  useEffect(() => {
    return () => {
      if (valueRef.current) URL.revokeObjectURL(valueRef.current.previewUrl);
    };
  }, []);

  function handleFile(file: File | null | undefined) {
    if (!file) return;
    setLocalError(null);

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setLocalError(`Please upload a ${ACCEPTED_LABEL} image.`);
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setLocalError("Image must be smaller than 8MB.");
      return;
    }

    if (value) URL.revokeObjectURL(value.previewUrl);
    onChange({ file, previewUrl: URL.createObjectURL(file) });
  }

  function handleRemove() {
    if (value) URL.revokeObjectURL(value.previewUrl);
    onChange(null);
    setLocalError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        className="sr-only"
        id="report-image-input"
        onChange={(event) => handleFile(event.target.files?.[0])}
      />

      {!value ? (
        <label
          htmlFor="report-image-input"
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragActive(false);
            handleFile(event.dataTransfer.files?.[0]);
          }}
          className={cn(
            "flex h-64 cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-4 text-center transition-colors",
            dragActive ? "border-primary bg-primary/5" : "border-border-subtle hover:bg-surface-container-low",
            localError && "border-error",
          )}
        >
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-container-low text-on-surface-variant">
            <CameraIcon className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-medium text-on-surface">Take a photo or upload one</p>
            <p className="mt-1 text-xs text-on-surface-variant">
              {ACCEPTED_LABEL}, up to 8MB
            </p>
          </div>
          <span className="rounded-md border border-on-surface px-3 py-1.5 text-sm font-medium text-on-surface">
            Select File
          </span>
        </label>
      ) : (
        <div className="relative overflow-hidden rounded-lg border border-border-subtle">
          {/* Local object URL preview — next/image can't optimize blob: URLs. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={value.previewUrl}
            alt="Uploaded road issue"
            className="h-64 w-full object-cover"
          />
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-inverse-surface/80 p-2 backdrop-blur-sm">
            <label
              htmlFor="report-image-input"
              className="cursor-pointer rounded-md bg-inverse-on-surface px-3 py-1.5 text-xs font-medium text-on-surface transition-colors hover:bg-surface-container-lowest"
            >
              Replace
            </label>
            <button
              type="button"
              onClick={handleRemove}
              className="flex items-center gap-1 rounded-md bg-inverse-on-surface px-3 py-1.5 text-xs font-medium text-error transition-colors hover:bg-surface-container-lowest"
            >
              <TrashIcon className="h-3.5 w-3.5" />
              Remove
            </button>
          </div>
        </div>
      )}

      {localError && <p className="mt-2 text-xs text-error">{localError}</p>}
      <p className="mt-2 text-xs text-on-surface-variant">
        Your photo is kept with this report on your device for reference. The RoadSense backend
        doesn&apos;t accept uploaded images yet, so it isn&apos;t sent to the server.
      </p>
    </div>
  );
}
