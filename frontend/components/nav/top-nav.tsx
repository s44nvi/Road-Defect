"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/cn";
import { clearSession } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { CarIcon, CompassIcon, BellIcon, SearchIcon, SettingsIcon, PlusIcon } from "@/components/icons";

interface TopNavProps {
  role: "citizen" | "officer";
  name: string;
  subtitle?: string;
}

const citizenLinks = [
  { href: "/home", label: "Home" },
  { href: "/my-reports", label: "My Reports" },
];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "?";
}

function IconButton({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      className="rounded-full p-2 text-on-surface-variant transition-colors hover:bg-surface-container-low"
    >
      {children}
    </button>
  );
}

function LogoutButton() {
  const router = useRouter();
  return (
    <Button
      variant="ghost"
      className="h-8 px-2 text-xs"
      onClick={() => {
        clearSession();
        router.push("/login");
      }}
    >
      Log out
    </Button>
  );
}

function Avatar({ name }: { name: string }) {
  return (
    <div className="flex h-9 w-9 items-center justify-center rounded-full border border-outline-variant bg-secondary-container text-xs font-semibold text-on-secondary-container">
      {initials(name)}
    </div>
  );
}

export function TopNav({ role, name, subtitle }: TopNavProps) {
  const pathname = usePathname();

  if (role === "officer") {
    return (
      <header className="sticky top-0 z-50 flex h-16 w-full items-center justify-between border-b border-outline-variant bg-surface-container-lowest px-margin-mobile shadow-sm md:px-margin-desktop">
        <div className="flex items-center gap-4">
          <CarIcon className="h-7 w-7 text-primary" />
          <span className="text-lg font-bold text-primary">RoadSense</span>
          <div className="hidden h-6 w-px bg-outline-variant md:block" />
          <span className="hidden text-sm text-secondary md:inline">{subtitle ?? "Municipal Command Center"}</span>
        </div>
        <div className="flex items-center gap-2">
          <IconButton label="Search">
            <SearchIcon className="h-5 w-5" />
          </IconButton>
          <IconButton label="Notifications">
            <BellIcon className="h-5 w-5" />
          </IconButton>
          <IconButton label="Settings">
            <SettingsIcon className="h-5 w-5" />
          </IconButton>
          <div className="flex items-center gap-2 border-l border-outline-variant pl-3">
            <div className="hidden text-right md:block">
              <p className="text-sm font-medium text-on-surface">{name}</p>
              <p className="text-xs text-secondary">Officer</p>
            </div>
            <Avatar name={name} />
          </div>
          <LogoutButton />
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-outline-variant bg-background shadow-sm">
      <div className="mx-auto flex h-16 max-w-container-max items-center justify-between px-margin-mobile md:px-margin-desktop">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-2">
            <CompassIcon className="h-6 w-6 text-primary" />
            <span className="text-lg font-semibold text-primary">RoadSense</span>
          </div>
          <nav className="hidden items-center gap-8 md:flex">
            {citizenLinks.map((link) => {
              const active = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={cn(
                    "flex h-16 items-center border-b-2 text-sm font-medium transition-colors",
                    active
                      ? "border-primary text-primary"
                      : "border-transparent text-on-surface-variant hover:text-primary",
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-1.5 sm:gap-3">
          <Link href="/report">
            <Button variant="primary" className="px-2.5 sm:px-4">
              <PlusIcon className="h-4 w-4" />
              <span className="hidden sm:inline">Report an Issue</span>
            </Button>
          </Link>
          <IconButton label="Notifications">
            <BellIcon className="h-5 w-5" />
          </IconButton>
          <Avatar name={name} />
          <LogoutButton />
        </div>
      </div>
    </header>
  );
}
