"use client";

import {
  createColumnHelper,
  createSortedRowModel,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_text,
  tableFeatures,
  useTable,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, BellRing, Ghost } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ScoreBadge, StatusBadge } from "@/components/common";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ApplicationSummary } from "@/lib/api";
import { formatDate, ROLE_FAMILY_LABEL } from "@/lib/format";

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  sortFns: { alphanumeric: sortFn_alphanumeric, text: sortFn_text },
});
const helper = createColumnHelper<typeof features, ApplicationSummary>();

// Dates as sortable numbers; missing dates sort last.
const time = (iso: string | null) => (iso ? new Date(iso).getTime() : undefined);

const columns = helper.columns([
  helper.accessor((row) => `${row.company} ${row.title}`, {
    id: "job",
    header: "Job",
    sortFn: "text",
    cell: ({ row }) => (
      <div className="min-w-48">
        <Link href={`/applications/${row.original.id}`} className="font-medium hover:underline">
          {row.original.title}
        </Link>
        <div className="text-xs text-muted-foreground">
          {[row.original.company, row.original.city].filter(Boolean).join(" · ")}
        </div>
      </div>
    ),
  }),
  helper.accessor("status", {
    header: "Status",
    sortFn: "text",
    cell: ({ row }) => (
      <div className="flex items-center gap-1.5">
        <StatusBadge status={row.original.status} />
        {row.original.follow_up_due && <BellRing className="size-3.5 text-amber-600" aria-label="Follow-up due" />}
        {row.original.suggest_ghosted && <Ghost className="size-3.5 text-muted-foreground" aria-label="Maybe ghosted" />}
      </div>
    ),
  }),
  helper.accessor("fit_score", {
    header: "Fit",
    cell: ({ row }) => <ScoreBadge score={row.original.fit_score} recommendation={row.original.recommendation} />,
  }),
  helper.accessor("source_portal", { header: "Portal", sortFn: "text", cell: (c) => c.getValue() || "–" }),
  helper.accessor("role_family", {
    header: "Type",
    sortFn: "text",
    cell: (c) => ROLE_FAMILY_LABEL[c.getValue()] ?? c.getValue(),
  }),
  helper.accessor((row) => time(row.applied_at), {
    id: "applied_at",
    header: "Applied",
    sortUndefined: "last",
    cell: ({ row }) => formatDate(row.original.applied_at),
  }),
  helper.accessor((row) => time(row.follow_up_at), {
    id: "follow_up_at",
    header: "Follow up",
    sortUndefined: "last",
    cell: ({ row }) => formatDate(row.original.follow_up_at),
  }),
  helper.accessor((row) => time(row.created_at), {
    id: "created_at",
    header: "Added",
    cell: ({ row }) => formatDate(row.original.created_at),
  }),
]);

export function ApplicationsTable({ data }: { data: ApplicationSummary[] }) {
  const router = useRouter();
  const table = useTable({
    features,
    columns,
    data,
    initialState: { sorting: [{ id: "created_at", desc: true }] },
    enableSortingRemoval: false,
  });

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((group) => (
            <TableRow key={group.id}>
              {group.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                return (
                  <TableHead key={header.id}>
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 hover:text-foreground"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <table.FlexRender header={header} />
                      {sorted === "asc" ? (
                        <ArrowUp className="size-3.5" />
                      ) : sorted === "desc" ? (
                        <ArrowDown className="size-3.5" />
                      ) : (
                        <ArrowUpDown className="size-3.5 opacity-40" />
                      )}
                    </button>
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow
              key={row.id}
              className="cursor-pointer"
              onClick={(e) => {
                if (!(e.target as HTMLElement).closest("a,button")) router.push(`/applications/${row.original.id}`);
              }}
            >
              {row.getAllCells().map((cell) => (
                <TableCell key={cell.id}>
                  <table.FlexRender cell={cell} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
