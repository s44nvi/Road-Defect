// Session persisted in this browser after a real login (POST
// /auth/officer/login or POST /auth/citizen/login). The JWT lives in
// localStorage rather than an httpOnly cookie — the backend has no cookie
// support today — so it is readable by any script on this origin; treat
// this as a known limitation, not a hardened auth store.

export type UserRole = "citizen" | "officer";

export interface Session {
  role: UserRole;
  name: string;
  email: string;
  userId: number;
  token: string;
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
      parsed.name.trim().length > 0 &&
      typeof parsed.token === "string" &&
      parsed.token.length > 0 &&
      typeof parsed.userId === "number" &&
      typeof parsed.email === "string"
    ) {
      return { role: parsed.role, name: parsed.name, email: parsed.email, userId: parsed.userId, token: parsed.token };
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
