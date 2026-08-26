"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { CarIcon, PersonIcon, ShieldIcon, CheckCircleIcon } from "@/components/icons";
import { cn } from "@/lib/cn";
import { homeRouteForRole, writeSession, type UserRole } from "@/lib/session";
import { officerLogin, citizenLogin, ApiError } from "@/lib/api";

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
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password) {
      setError("Enter your email and password to continue.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (role === "officer") {
        const response = await officerLogin({ email: trimmedEmail, password });
        writeSession({
          role: "officer",
          name: response.officer.name,
          email: response.officer.email,
          userId: response.officer.officer_id,
          token: response.access_token,
        });
      } else {
        const response = await citizenLogin({ email: trimmedEmail, password });
        writeSession({
          role: "citizen",
          name: response.citizen.name,
          email: response.citizen.email,
          userId: response.citizen.citizen_id,
          token: response.access_token,
        });
      }
      router.push(homeRouteForRole(role));
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 401 || err.status === 422
            ? "Incorrect email or password."
            : err.message
          : "Something went wrong signing in. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
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
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="jane@example.com"
                  value={email}
                  onChange={(event) => {
                    setEmail(event.target.value);
                    if (error) setError(null);
                  }}
                  autoComplete="email"
                />
              </div>
              <div>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    if (error) setError(null);
                  }}
                  autoComplete="current-password"
                />
              </div>
            </div>

            {error && (
              <p className="rounded-md bg-error-container px-3 py-2 text-sm text-on-error-container">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Signing in…" : "Continue"}
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-on-surface-variant">
            Signs in against the real RoadSense backend. Your session token is stored only in this
            browser.
          </p>
        </Card>
      </div>
    </main>
  );
}
