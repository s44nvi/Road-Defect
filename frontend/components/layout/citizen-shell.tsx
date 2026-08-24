import { TopNav } from "@/components/nav/top-nav";

export function CitizenShell({
  name,
  children,
}: {
  name: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-background">
      <TopNav role="citizen" name={name} />
      {children}
    </div>
  );
}
