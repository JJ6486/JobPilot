import type { EventOut } from "@/lib/api";
import { formatDateTime, STATUS_LABEL } from "@/lib/format";
import type { Status } from "@/lib/api";

function describe(e: EventOut): string {
  switch (e.type) {
    case "created":
      return e.note || "Analysed";
    case "status_change": {
      const to = STATUS_LABEL[e.to_status as Status] ?? e.to_status;
      const from = e.from_status ? STATUS_LABEL[e.from_status as Status] ?? e.from_status : null;
      return `${from ? `${from} → ` : ""}${to}${e.note ? ` · ${e.note}` : ""}`;
    }
    case "note":
      return `Note: ${e.note}`;
    default:
      return e.note || e.type;
  }
}

export function Timeline({ events }: { events: EventOut[] }) {
  return (
    <ol className="relative space-y-3 border-l pl-4">
      {[...events].reverse().map((e) => (
        <li key={e.id} className="relative text-sm">
          <span className="absolute top-1.5 -left-[21px] size-2 rounded-full bg-primary" />
          <p className="wrap-break-word">{describe(e)}</p>
          <p className="text-xs text-muted-foreground">{formatDateTime(e.created_at)}</p>
        </li>
      ))}
    </ol>
  );
}
