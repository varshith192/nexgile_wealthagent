"use client";

/**
 * Approvals (§37).
 *
 * One queue for every reviewable action — recommendations, rebalances,
 * harvests, beneficiary changes, distributions. The available transitions come
 * from the server, so the UI can never offer an action the caller cannot take.
 */

import { useMemo, useState } from "react";
import { BadgeCheck, CircleSlash, Play, ShieldCheck, ThumbsDown, ThumbsUp } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatDateTime, titleCase } from "@/lib/format";
import type { Approval, ApprovalStatus } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Drawer, Textarea, Tabs } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type ApprovalsPayload = {
  approvals: Approval[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  pending_count: number;
};

const TRANSITION_LABELS: Record<string, { label: string; endpoint: string; variant: "primary" | "secondary" | "danger" | "ghost"; icon: React.ComponentType<{ className?: string }> }> = {
  submitted: { label: "Submit for review", endpoint: "submit", variant: "primary", icon: Play },
  under_review: { label: "Start review", endpoint: "review", variant: "secondary", icon: ShieldCheck },
  approved: { label: "Approve", endpoint: "approve", variant: "primary", icon: ThumbsUp },
  rejected: { label: "Reject", endpoint: "reject", variant: "danger", icon: ThumbsDown },
  completed: { label: "Mark completed", endpoint: "complete", variant: "primary", icon: BadgeCheck },
  cancelled: { label: "Cancel", endpoint: "transition", variant: "ghost", icon: CircleSlash },
};

export default function ApprovalsPage() {
  const [tab, setTab] = useState("open");
  const [selected, setSelected] = useState<Approval | null>(null);

  const statusFilter = tab === "open" ? "" : tab;
  const path = useMemo(
    () => (statusFilter ? `/api/approvals?status_filter=${statusFilter}&page_size=100` : "/api/approvals?page_size=100"),
    [statusFilter],
  );
  const { data, error, loading, refetch } = useApi<ApprovalsPayload>(path);

  const visible = useMemo(() => {
    if (!data) return [];
    if (tab === "open") {
      return data.approvals.filter((approval) => ["draft", "submitted", "under_review"].includes(approval.status));
    }
    return data.approvals;
  }, [data, tab]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Approvals"
        description="Every action that changes something moves through this queue. Nothing bypasses it."
      />

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Awaiting a decision" value={String(data.pending_count)} tone={data.pending_count ? "warning" : "positive"} icon={BadgeCheck} />
          <StatTile label="Total requests" value={String(data.total)} />
          <StatTile
            label="Approved"
            value={String(data.approvals.filter((approval) => approval.status === "approved").length)}
            tone="positive"
          />
          <StatTile
            label="Completed"
            value={String(data.approvals.filter((approval) => approval.status === "completed").length)}
          />
        </StatRow>
      ) : null}

      <Card>
        <div className="px-5 pt-4">
          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[
              { value: "open", label: "Open" },
              { value: "submitted", label: "Submitted" },
              { value: "under_review", label: "Under review" },
              { value: "approved", label: "Approved" },
              { value: "completed", label: "Completed" },
              { value: "rejected", label: "Rejected" },
            ]}
          />
        </div>

        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={6} />}
          emptyWhen={() => visible.length === 0}
          empty={<EmptyState icon={BadgeCheck} title="Nothing in this queue" description="Requests appear here as they are raised." />}
        >
          {() => (
            <ul className="divide-y divide-border">
              {visible.map((approval) => (
                <li key={approval.id}>
                  <button
                    onClick={() => setSelected(approval)}
                    className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-surface-muted/70"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={approval.status} />
                        <Badge tone="outline" size="sm">{titleCase(approval.entity_type)}</Badge>
                        <Badge tone={approval.priority === "high" ? "warning" : "outline"} size="sm">
                          {titleCase(approval.priority)} priority
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm font-medium text-ink">{approval.title}</p>
                      {approval.summary ? (
                        <p className="mt-0.5 max-w-3xl text-xs leading-5 text-ink-muted">{approval.summary}</p>
                      ) : null}
                      <p className="mt-1.5 text-2xs text-ink-subtle">
                        {approval.household ? `${approval.household} · ` : ""}
                        raised by {approval.requested_by}
                        {approval.submitted_at ? ` · submitted ${formatDate(approval.submitted_at)}` : ""}
                        {approval.due_date ? ` · due ${formatDate(approval.due_date)}` : ""}
                      </p>
                    </div>
                    {approval.estimated_impact !== null ? (
                      <div className="shrink-0 text-right">
                        <p className="section-label">Estimated impact</p>
                        <p className="mt-1 text-base font-semibold tabular text-ink">
                          {formatCurrency(approval.estimated_impact, { compact: true })}
                        </p>
                      </div>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </DataState>
      </Card>

      <ApprovalDrawer
        approval={selected}
        onClose={() => setSelected(null)}
        onChanged={(updated) => {
          setSelected(updated);
          refetch();
        }}
      />
    </div>
  );
}

function ApprovalDrawer({
  approval,
  onClose,
  onChanged,
}: {
  approval: Approval | null;
  onClose: () => void;
  onChanged: (approval: Approval) => void;
}) {
  const [note, setNote] = useState("");

  const { run: act, pending, message } = useMutation(async (target: ApprovalStatus) => {
    if (!approval) return null;
    const config = TRANSITION_LABELS[target];
    const body = config.endpoint === "transition" ? { to_status: target, note: note || null } : { note: note || null };
    const updated = await api.post<Approval>(`/api/approvals/${approval.id}/${config.endpoint}`, body);
    setNote("");
    onChanged(updated);
    return updated;
  });

  if (!approval) return <Drawer open={false} onClose={onClose} title="Approval">{null}</Drawer>;

  return (
    <Drawer
      open
      onClose={onClose}
      title={approval.title}
      description={`${titleCase(approval.entity_type)} · ${approval.household ?? "Platform"}`}
      width="max-w-2xl"
      footer={
        approval.available_transitions.length > 0 ? (
          <div className="space-y-3">
            <Textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={2}
              placeholder="Add a decision note (recorded in the audit trail)…"
              aria-label="Decision note"
            />
            <div className="flex flex-wrap gap-2">
              {approval.available_transitions.map((target) => {
                const config = TRANSITION_LABELS[target];
                if (!config) return null;
                const Icon = config.icon;
                return (
                  <Button key={target} size="sm" variant={config.variant} loading={pending} onClick={() => act(target)}>
                    <Icon />
                    {config.label}
                  </Button>
                );
              })}
            </div>
            {message ? <p className="text-xs text-negative">{message}</p> : null}
          </div>
        ) : (
          <p className="text-xs text-ink-muted">
            This request has reached a terminal state. No further transitions are available.
          </p>
        )
      }
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={approval.status} />
          <Badge tone="outline">{titleCase(approval.entity_type)}</Badge>
          <Badge tone={approval.priority === "high" ? "warning" : "outline"}>{titleCase(approval.priority)} priority</Badge>
          <Badge tone="outline">Decided by {titleCase(approval.required_role)}</Badge>
        </div>

        {approval.summary ? (
          <section>
            <h3 className="section-label">Request</h3>
            <p className="mt-1.5 text-sm leading-6 text-ink-muted">{approval.summary}</p>
          </section>
        ) : null}

        <section>
          <h3 className="section-label">Details</h3>
          <KeyValue
            className="mt-2.5"
            items={[
              { label: "Requested by", value: approval.requested_by },
              { label: "Raised", value: formatDate(approval.created_at) },
              { label: "Submitted", value: approval.submitted_at ? formatDate(approval.submitted_at) : "—" },
              { label: "Due", value: approval.due_date ? formatDate(approval.due_date) : "—" },
              { label: "Decided by", value: approval.decided_by ?? "—" },
              { label: "Decided", value: approval.decided_at ? formatDate(approval.decided_at) : "—" },
              {
                label: "Estimated impact",
                value: approval.estimated_impact !== null ? formatCurrency(approval.estimated_impact) : "—",
              },
              { label: "Completed", value: approval.completed_at ? formatDate(approval.completed_at) : "—" },
            ]}
          />
        </section>

        {approval.decision_note ? (
          <section className="rounded-md border border-border bg-surface-muted/60 p-3.5">
            <h3 className="section-label">Decision note</h3>
            <p className="mt-1.5 text-sm leading-6 text-ink">{approval.decision_note}</p>
          </section>
        ) : null}

        <section>
          <h3 className="section-label">History</h3>
          <ol className="mt-3 space-y-0">
            {approval.events.map((event, index) => (
              <li key={event.id} className="relative flex gap-3.5 pb-5 last:pb-0">
                {index < approval.events.length - 1 ? (
                  <span className="absolute left-[0.4375rem] top-4 h-full w-px bg-border" aria-hidden />
                ) : null}
                <span
                  className={cn(
                    "relative mt-1 size-3.5 shrink-0 rounded-full border-2 border-surface",
                    event.to_status === "approved" || event.to_status === "completed"
                      ? "bg-positive"
                      : event.to_status === "rejected" || event.to_status === "cancelled"
                        ? "bg-negative"
                        : "bg-primary",
                  )}
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                    {event.from_status ? `${titleCase(event.from_status)} → ` : ""}
                    {titleCase(event.to_status)}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {event.actor_name} · {formatDateTime(event.created_at)}
                  </p>
                  {event.note ? <p className="mt-1 text-xs leading-5 text-ink-muted">{event.note}</p> : null}
                </div>
              </li>
            ))}
          </ol>
        </section>

        {approval.payload && Object.keys(approval.payload).length > 0 ? (
          <section>
            <h3 className="section-label">Linked record</h3>
            <dl className="mt-2 space-y-1.5">
              {Object.entries(approval.payload).map(([key, value]) => (
                <div key={key} className="flex items-baseline justify-between gap-4 border-b border-border/60 pb-1">
                  <dt className="text-xs text-ink-muted">{titleCase(key)}</dt>
                  <dd className="max-w-[60%] truncate text-right text-xs text-ink">
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ) : null}
      </div>
    </Drawer>
  );
}
