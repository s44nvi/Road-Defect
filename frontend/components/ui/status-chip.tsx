import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

// Pill-shaped status badges per DESIGN.md: 10%-opacity tint of the status
// color for the background, full-opacity for the text.
export type StatusTone = "neutral" | "info" | "success" | "warning" | "critical";

const toneClasses: Record<StatusTone, string> = {
  neutral: "bg-on-surface-variant/10 text-on-surface-variant",
  info: "bg-secondary/10 text-secondary",
  success: "bg-primary/10 text-primary",
  warning: "bg-tertiary/10 text-tertiary",
  critical: "bg-error/10 text-error",
};

export function StatusChip({
  tone = "neutral",
  children,
  className,
}: {
  tone?: StatusTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
