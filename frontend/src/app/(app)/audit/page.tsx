"use client";

/** Audit trail (§38): who did what, to which record, when, and what changed. */

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ListChecks, ShieldCheck } from "lucide-react";

import { formatDateTime, formatRelative, titleCase } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardHeader, Input, Select } from "@/components/ui";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type AuditPayload = {
  events: AuditEvent[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

const ACTIONS = [
  "",
  "login",
  "login_failed",
  "document_upload",
  "document_classify",
  "recommendation_created",
  "approval_submitted",
  "approval_reviewed",
  "approval_decided",
  "approval_completed",
  "beneficiary_change",
  "rebalance_created",
  "rebalance_executed",
  "harvest_created",
  "harvest_executed",
  "scenario_run",
  "report_generated",
  "compliance_action",
  "goal_updated",
];

const ENTITY_TYPES = [
  "",
  "account",
  "approval",
  "beneficiary",
  "compliance_test",
  "document",
  "goal",
  "harvest",
  "rebalance",
  "recommendation",
  "report",
  "session",
];

export default function AuditPage() {
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const path = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "50" });
    if (action) params.set("action", action);
    if (entityType) params.set("entity_type", entityType);
    return `/api/audit?${params.toString()}`;
  }, [action, entityType, page]);

  const { data, error, loading, refetch } = useApi<AuditPayload>(path);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit trail"
        description="An append-only record of every consequential action in the platform: who did it, to which record, and what changed."
        meta={
          <span className="flex items-center gap-1.5 text-xs text-ink-muted">
            <ShieldCheck className="size-3.5 text-primary" aria-hidden />
            Events are written as actions happen and are never edited or removed.
          </span>
        }
      />

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Events recorded" value={String(data.total)} icon={ListChecks} tone="primary" />
          <StatTile
            label="Approvals decided"
            value={String(data.events.filter((event) => event.action === "approval_decided").length)}
            hint="On this page"
          />
          <StatTile
            label="Failed sign-ins"
            value={String(data.events.filter((event) => event.status === "failed").length)}
            hint="On this page"
            tone={data.events.some((event) => event.status === "failed") ? "warning" : "positive"}
          />
          <StatTile label="Pages" value={String(data.pages)} hint={`${data.page_size} events per page`} />
        </StatRow>
      ) : null}

      <Card>
        <CardHeader
          title="Activity"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={action}
                onChange={(event) => {
                  setAction(event.target.value);
                  setPage(1);
                }}
                className="h-8 w-52 text-xs"
                aria-label="Filter by action"
              >
                {ACTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option ? titleCase(option) : "All actions"}
                  </option>
                ))}
              </Select>
              <Select
                value={entityType}
                onChange={(event) => {
                  setEntityType(event.target.value);
                  setPage(1);
                }}
                className="h-8 w-44 text-xs"
                aria-label="Filter by record type"
              >
                {ENTITY_TYPES.map((option) => (
                  <option key={option} value={option}>
                    {option ? titleCase(option) : "All record types"}
                  </option>
                ))}
              </Select>
            </div>
          }
        />

        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={10} />}
          emptyWhen={(payload) => payload.events.length === 0}
          empty={<EmptyState icon={ListChecks} title="No matching events" description="Adjust the filters to see more activity." />}
        >
          {(payload) => (
            <>
              <ol className="divide-y divide-border">
                {payload.events.map((event) => {
                  const open = expanded === event.id;
                  const hasDiff = Boolean(event.before_state || event.after_state);
                  return (
                    <li key={event.id}>
                      <button
                        onClick={() => hasDiff && setExpanded(open ? null : event.id)}
                        className={cn(
                          "flex w-full items-start gap-4 px-5 py-3.5 text-left transition-colors",
                          hasDiff ? "cursor-pointer hover:bg-surface-muted/70" : "cursor-default",
                        )}
                      >
                        <span
                          className={cn(
                            "mt-1.5 size-2 shrink-0 rounded-full",
                            event.status === "failed" ? "bg-negative" : "bg-primary",
                          )}
                          aria-hidden
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={event.status === "failed" ? "negative" : "outline"} size="sm">
                              {titleCase(event.action)}
                            </Badge>
                            <Badge tone="outline" size="sm">{titleCase(event.entity_type)}</Badge>
                          </div>
                          <p className="mt-1.5 text-sm text-ink">
                            {event.summary ?? `${titleCase(event.action)} on ${event.entity_label ?? event.entity_type}`}
                          </p>
                          <p className="mt-0.5 text-xs text-ink-muted">
                            <span className="font-medium text-ink">{event.actor_name}</span>
                            {event.actor_role ? ` (${titleCase(event.actor_role)})` : ""} · {formatDateTime(event.created_at)}
                            {event.ip_address ? ` · ${event.ip_address}` : ""}
                          </p>
                        </div>
                        <span className="shrink-0 text-2xs text-ink-subtle">{formatRelative(event.created_at)}</span>
                      </button>

                      {open && hasDiff ? (
                        <div className="animate-slide-up border-t border-border bg-surface-muted/50 px-5 py-4">
                          <div className="grid gap-4 sm:grid-cols-2">
                            <StateBlock label="Before" state={event.before_state} tone="negative" />
                            <StateBlock label="After" state={event.after_state} tone="positive" />
                          </div>
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ol>

              <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
                <p className="text-xs text-ink-muted">
                  Page {payload.page} of {payload.pages} · {payload.total} events
                </p>
                <div className="flex items-center gap-1.5">
                  <Button size="sm" variant="ghost" disabled={payload.page <= 1} onClick={() => setPage((value) => value - 1)}>
                    <ChevronLeft />
                    Previous
                  </Button>
                  <Button size="sm" variant="ghost" disabled={payload.page >= payload.pages} onClick={() => setPage((value) => value + 1)}>
                    Next
                    <ChevronRight />
                  </Button>
                </div>
              </div>
            </>
          )}
        </DataState>
      </Card>
    </div>
  );
}

function StateBlock({
  label,
  state,
  tone,
}: {
  label: string;
  state: Record<string, unknown> | null;
  tone: "positive" | "negative";
}) {
  return (
    <div>
      <p className="section-label">{label}</p>
      {!state || Object.keys(state).length === 0 ? (
        <p className="mt-1.5 text-xs text-ink-subtle">Not recorded</p>
      ) : (
        <dl
          className={cn(
            "mt-1.5 space-y-1 rounded-md border px-3 py-2",
            tone === "positive" ? "border-positive/20 bg-positive-soft/50" : "border-border bg-surface",
          )}
        >
          {Object.entries(state).map(([key, value]) => (
            <div key={key} className="flex items-baseline justify-between gap-3">
              <dt className="text-2xs text-ink-muted">{titleCase(key)}</dt>
              <dd className="max-w-[60%] truncate text-right text-2xs font-medium tabular text-ink">
                {value === null || value === undefined
                  ? "—"
                  : typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
