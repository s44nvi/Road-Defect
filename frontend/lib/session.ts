// Local-only demo session. The backend has no auth endpoints, so this is
// NOT real authentication — it just remembers a name/role choice in this
// browser so the citizen/officer UIs and route gating have something to
// key off of.

export type UserRole = "citizen" | "officer";

export interface Session {
  role: UserRole;
  name: string;
}

const STORAGE_KEY = "roadsense.session";

export function readSession(): Session | null {
  if (typeof window === "undefined") return null;

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<Session>;
    if (
      (parsed.role === "citizen" || parsed.role === "officer") &&
      typeof parsed.name === "string" &&
      parsed.name.trim().length > 0
    ) {
      return { role: parsed.role, name: parsed.name };
    }
    return null;
  } catch {
    return null;
  }
}

export function writeSession(session: Session): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export function homeRouteForRole(role: UserRole): string {
  return role === "officer" ? "/dashboard" : "/home";
}

export const SESSION_STORAGE_KEY = STORAGE_KEY;
