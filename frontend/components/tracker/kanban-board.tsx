"use client";

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { BellRing } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ScoreBadge } from "@/components/common";
import { STATUSES, type ApplicationSummary, type Status } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/format";
import { cn } from "@/lib/utils";

function CardBody({ app }: { app: ApplicationSummary }) {
  return (
    <>
      <p className="text-sm leading-snug font-medium">{app.title}</p>
      <p className="text-xs text-muted-foreground">{app.company || "–"}</p>
      <div className="mt-2 flex items-center justify-between">
        <ScoreBadge score={app.fit_score} recommendation={app.recommendation} />
        {app.follow_up_due && <BellRing className="size-3.5 text-amber-600" aria-label="Follow-up due" />}
      </div>
    </>
  );
}

function DraggableCard({ app }: { app: ApplicationSummary }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: app.id });
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={cn(
        "cursor-grab rounded-md border bg-card p-2.5 shadow-xs active:cursor-grabbing",
        isDragging && "opacity-40",
      )}
    >
      <Link href={`/applications/${app.id}`} className="block" draggable={false}>
        <CardBody app={app} />
      </Link>
    </div>
  );
}

function Column({ status, apps }: { status: Status; apps: ApplicationSummary[] }) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-60 shrink-0 flex-col gap-2 rounded-lg border bg-muted/40 p-2 transition-colors",
        isOver && "border-primary bg-primary/5",
      )}
    >
      <div className="flex items-center justify-between px-1 pt-0.5">
        <span className="text-sm font-medium">{STATUS_LABEL[status]}</span>
        <span className="text-xs text-muted-foreground tabular-nums">{apps.length}</span>
      </div>
      <div className="flex min-h-24 flex-col gap-2">
        {apps.map((a) => (
          <DraggableCard key={a.id} app={a} />
        ))}
      </div>
    </div>
  );
}

/** Drag cards between status columns; each move is saved (and logged) through `onMove`. */
export function KanbanBoard({
  data,
  onMove,
}: {
  data: ApplicationSummary[];
  onMove: (id: number, status: Status) => void;
}) {
  // A small drag distance keeps plain clicks working as links.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );
  const [active, setActive] = useState<ApplicationSummary | null>(null);

  const onDragStart = (e: DragStartEvent) => setActive(data.find((a) => a.id === e.active.id) ?? null);
  const onDragEnd = (e: DragEndEvent) => {
    setActive(null);
    const app = data.find((a) => a.id === e.active.id);
    const target = e.over?.id as Status | undefined;
    if (app && target && target !== app.status) onMove(app.id, target);
  };

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setActive(null)}>
      <div className="flex gap-3 overflow-x-auto pb-3">
        {STATUSES.map((s) => (
          <Column key={s} status={s} apps={data.filter((a) => a.status === s)} />
        ))}
      </div>
      <DragOverlay>
        {active && (
          <div className="w-56 rounded-md border bg-card p-2.5 shadow-lg">
            <CardBody app={active} />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
