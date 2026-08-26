import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PlusIcon, CompassIcon } from "@/components/icons";

export function MyReportsEmptyState() {
  return (
    <Card className="mx-auto max-w-md p-10 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
        <CompassIcon className="h-6 w-6" />
      </div>
      <h2 className="mt-4 text-lg font-semibold text-on-surface">No reports yet</h2>
      <p className="mt-2 text-sm text-on-surface-variant">
        Report a road issue and track its progress here.
      </p>
      <Link href="/report" className="mt-6 inline-block">
        <Button variant="primary">
          <PlusIcon className="h-4 w-4" />
          Report an Issue
        </Button>
      </Link>
    </Card>
  );
}
