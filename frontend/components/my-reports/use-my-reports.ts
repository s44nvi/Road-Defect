"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchMyReports, ApiError, type DefectResponseWithPriority } from "@/lib/api";

type MyReportsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; defects: DefectResponseWithPriority[] };

// GET /reports/mine — user-scoped in the database query (not filtered
// client-side), requires the citizen's bearer token. Only defects created
// through the authenticated POST /reports/image path are associated with
// a citizen; reports made through the anonymous JSON POST /reports never
// appear here (a backend/product decision, not a frontend limitation).
export function useMyReports(token: string): MyReportsState & { reload: () => void } {
  const [state, setState] = useState<MyReportsState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });

    fetchMyReports(token)
      .then((defects) => {
        if (!cancelled) setState({ status: "ready", defects });
      })
      .catch((error) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: error instanceof ApiError ? error.message : "Failed to load your reports.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token, reloadToken]);

  const reload = useCallback(() => setReloadToken((t) => t + 1), []);

  return { ...state, reload };
}
