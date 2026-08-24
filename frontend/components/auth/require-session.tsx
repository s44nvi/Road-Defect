"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "@/lib/use-session";
import { homeRouteForRole, type Session, type UserRole } from "@/lib/session";

// Client-side-only route gating against the local demo session. This is NOT
// real authentication or authorization — there is no server checking these
// routes, so it only guards against accidentally landing on the wrong
// screen in this demo, not against a motivated user editing localStorage.
export function RequireSession({
  role,
  children,
}: {
  role: UserRole;
  children: (session: Session) => React.ReactNode;
}) {
  const session = useSession();
  const router = useRouter();

  useEffect(() => {
    if (session === null) {
      router.replace("/login");
    } else if (session && session.role !== role) {
      router.replace(homeRouteForRole(session.role));
    }
  }, [session, role, router]);

  if (!session || session.role !== role) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-on-surface-variant">Loading…</p>
      </div>
    );
  }

  return <>{children(session)}</>;
}
