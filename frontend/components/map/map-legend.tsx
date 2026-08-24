import { Card } from "@/components/ui/card";

const legendItems: { label: string; dotClass: string }[] = [
  { label: "Critical", dotClass: "bg-error" },
  { label: "Medium", dotClass: "bg-tertiary" },
  { label: "Low", dotClass: "bg-inverse-primary" },
];

export function MapLegend() {
  return (
    <Card className="px-3 py-2">
      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant">
        Severity
      </p>
      <div className="flex items-center gap-3">
        {legendItems.map((item) => (
          <span key={item.label} className="flex items-center gap-1.5 text-xs text-on-surface">
            <span className={`h-2.5 w-2.5 rounded-full ${item.dotClass}`} />
            {item.label}
          </span>
        ))}
      </div>
    </Card>
  );
}
