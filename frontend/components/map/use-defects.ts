"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchDefects, type DefectResponseWithPriority } from "@/lib/api";
import { MOCK_DEFECTS } from "@/lib/mock-defects";

// Opt-in, dev-only fallback — see lib/mock-defects.ts. Off by default, so
// a genuinely unreachable backend always surfaces as a real error state
// (see the "error" branch below) instead of silently showing sample data.
const USE_MOCK_FALLBACK = process.env.NEXT_PUBLIC_ENABLE_DEFECT_MOCK === "true";

type DefectsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; defects: DefectResponseWithPriority[]; usingMock: boolean };

export function useDefects(): DefectsState & { reload: () => void } {
  const [state, setState] = useState<DefectsState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    fetchDefects()
      .then((defects) => {
        if (!cancelled) setState({ status: "ready", defects, usingMock: false });
      })
      .catch((error) => {
        if (cancelled) return;
        if (USE_MOCK_FALLBACK) {
          setState({ status: "ready", defects: MOCK_DEFECTS, usingMock: true });
        } else {
          setState({
            status: "error",
            message: error instanceof Error ? error.message : "Failed to load defects.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { ...state, reload };
}
