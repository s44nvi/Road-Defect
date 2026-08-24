import { TopNav } from "@/components/nav/top-nav";

export function OfficerShell({
  name,
  subtitle,
  children,
}: {
  name: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <TopNav role="officer" name={name} subtitle={subtitle} />
      {children}
    </div>
  );
}
