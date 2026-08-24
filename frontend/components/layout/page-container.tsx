import { type HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export function PageContainer({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "mx-auto w-full max-w-container-max px-margin-mobile md:px-margin-desktop",
        className,
      )}
      {...props}
    />
  );
}
