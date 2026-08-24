"use client";

import { useEffect, useState } from "react";
import { readSession, Session, SESSION_STORAGE_KEY } from "./session";

/**
 * `undefined` = not checked yet (avoids a logged-out flash during hydration),
 * `null` = confirmed logged out, `Session` = confirmed logged in.
 */
export function useSession(): Session | null | undefined {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    setSession(readSession());

    function onStorage(event: StorageEvent) {
      if (event.key === null || event.key === SESSION_STORAGE_KEY) {
        setSession(readSession());
      }
    }

    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  return session;
}
