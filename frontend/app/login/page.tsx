"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { CarIcon, PersonIcon, ShieldIcon, CheckCircleIcon } from "@/components/icons";
import { cn } from "@/lib/cn";
import { homeRouteForRole, writeSession, type UserRole } from "@/lib/session";

const roleOptions: {
  value: UserRole;
  label: string;
  hint?: string;
  icon: typeof PersonIcon;
}[] = [
  { value: "citizen", label: "I'm a Citizen", icon: PersonIcon },
  {
    value: "officer",
    label: "I'm a Municipal Officer",
    hint: "Officer accounts require municipal authorization",
    icon: ShieldIcon,
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [role, setRole] = useState<UserRole>("citizen");
  const [name, setName] = useState("");
  const [contact, setContact] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Enter your name to continue.");
      return;
    }
    writeSession({ role, name: trimmed });
    router.push(homeRouteForRole(role));
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-margin-mobile py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-primary shadow-card">
            <CarIcon className="h-6 w-6 text-on-primary" />
          </div>
          <h1 className="text-3xl font-bold text-on-surface">RoadSense</h1>
          <p className="mt-2 text-sm text-on-surface-variant">AI-powered road health intelligence</p>
        </div>

        <Card className="p-gutter">
          <h2 className="mb-6 text-center text-xl font-semibold text-on-surface">Sign in to RoadSense</h2>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {roleOptions.map((option) => {
                const selected = role === option.value;
                const Icon = option.icon;
                return (
                  <label key={option.value} className="relative cursor-pointer">
                    <input
                      type="radio"
                      name="role"
                      value={option.value}
                      checked={selected}
                      onChange={() => setRole(option.value)}
                      className="peer sr-only"
                    />
                    <div
                      className={cn(
                        "flex h-full flex-col items-center justify-center gap-2 rounded-xl border p-4 text-center transition-all hover:bg-surface-container-low",
                        selected
                          ? "border-primary bg-primary/10"
                          : "border-border-subtle",
                      )}
                    >
                      <Icon className={cn("h-6 w-6", selected ? "text-primary" : "text-on-surface-variant")} />
                      <span className="block text-sm font-medium text-on-surface">{option.label}</span>
                      {option.hint && (
                        <span className="block text-xs leading-tight text-on-surface-variant">
                          {option.hint}
                        </span>
                      )}
                    </div>
                    {selected && (
                      <div className="absolute right-2 top-2 text-primary">
                        <CheckCircleIcon className="h-[18px] w-[18px]" />
                      </div>
                    )}
                  </label>
                );
              })}
            </div>

            <div className="space-y-4">
              <div>
                <Label htmlFor="name">Full Name</Label>
                <Input
                  id="name"
                  placeholder="Jane Doe"
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    if (error) setError(null);
                  }}
                  autoComplete="name"
                />
              </div>
              <div>
                <Label htmlFor="contact">Email or Phone (optional)</Label>
                <Input
                  id="contact"
                  placeholder="jane@example.com"
                  value={contact}
                  onChange={(event) => setContact(event.target.value)}
                  autoComplete="email"
                />
              </div>
            </div>

            {error && (
              <p className="rounded-md bg-error-container px-3 py-2 text-sm text-on-error-container">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full">
              Continue
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-on-surface-variant">
            This is a local demo session stored only in your browser — RoadSense does not have a
            real account system yet.
          </p>
        </Card>
      </div>
    </main>
  );
}
