"use client";

/**
 * Admin / leadership overview.
 *
 * The firm-wide view: assets under advice, workflow throughput, compliance
 * posture and platform configuration. Every figure is read from the same APIs
 * the specialist workspaces use, so leadership and the desk never disagree.
 */

import Link from "next/link";
import {
  Activity,
  BadgeCheck,
  Building2,
  ChevronRight,
  Cpu,
  Database,
  Lightbulb,
  ListChecks,
  ScrollText,
  ShieldCheck,
  TrendingUp,
  Users,
} from "lucide-react";

import { API_URL } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCurrency, formatDateTime, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, TD, TH, THead, TR, Table } from "@/components/ui";
import { CategoryBars } from "@/components/charts";
import { SeverityBadge, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type AdvisorDashboard = {
  summary: {
    client_count: number;
    total_aum: number;
    average_relationship: number;
    pending_approvals: number;
    open_alerts: number;
    open_tasks: number;
    overdue_tasks: number;
    goals_off_track: number;
    opportunity_value: number;
  };
  clients: {
    household_id: string;
    name: string;
    segment: string;
    total_assets: number;
    net_worth: number;
    goals_off_track: number;
    pending_approvals: number;
  }[];
};

type ApprovalsPayload = {
  approvals: { id: string; status: string; entity_type: string; title: string; household: string | null }[];
  total: number;
  pending_count: number;
};

type Plan = { id: string; name: string; total_assets: number; participating_employees: number; participation_rate: number };

type Health = {
  status: string;
  version: string;
  environment: string;
  database: string;
  auth_provider: string;
  ai_provider: string;
  ai_mode: string;
  ai_key_configured: boolean;
  seeded: boolean;
  timestamp: string;
};

export default function AdminPage() {
  const { user } = useAuth();
  const book = useApi<AdvisorDashboard>("/api/advisor");
  const approvals = useApi<ApprovalsPayload>("/api/approvals?page_size=100");
  const plans = useApi<Plan[]>("/api/plans");
  const audit = useApi<{ events: AuditEvent[]; total: number }>("/api/audit?page_size=12");
  const health = useApi<Health>("/health");

  return (
    <div className="space-y-8">
      <PageHeader
        title="Leadership overview"
        description={`${user?.full_name ?? "Admin"} · firm-wide position across private clients, institutional plans and the approval pipeline.`}
        meta={
          health.data ? (
            <>
              <Badge tone={health.data.status === "ok" ? "positive" : "warning"}>
                <ShieldCheck className="size-3" />
                Platform {health.data.status}
              </Badge>
              <Badge tone="outline">v{health.data.version}</Badge>
              <Badge tone="outline">{titleCase(health.data.environment)}</Badge>
            </>
          ) : undefined
        }
        actions={
          <>
            <Link href="/approvals">
              <Button size="sm">
                <BadgeCheck />
                Approvals
              </Button>
            </Link>
            <Link href="/audit">
              <Button variant="primary" size="sm">
                <ListChecks />
                Audit trail
              </Button>
            </Link>
          </>
        }
      />

      {/* --------------------------------------------------- Firm position */}
      <DataState
        loading={book.loading}
        error={book.error}
        data={book.data}
        onRetry={book.refetch}
        loadingFallback={<LoadingGrid count={5} />}
      >
        {(dashboard) => {
          const planAssets = (plans.data ?? []).reduce((total, plan) => total + plan.total_assets, 0);
          const participants = (plans.data ?? []).reduce((total, plan) => total + plan.participating_employees, 0);

          return (
            <>
              <StatRow columns={5}>
                <StatTile
                  label="Private client AUM"
                  value={formatCurrency(dashboard.summary.total_aum, { compact: true })}
                  hint={`${dashboard.summary.client_count} households`}
                  icon={TrendingUp}
                  tone="primary"
                  href="/advisor/clients"
                />
                <StatTile
                  label="Institutional assets"
                  value={formatCurrency(planAssets, { compact: true })}
                  hint={`${formatNumber(participants)} participants`}
                  icon={Building2}
                  href="/institutional"
                />
                <StatTile
                  label="Average relationship"
                  value={formatCurrency(dashboard.summary.average_relationship, { compact: true })}
                  icon={Users}
                />
                <StatTile
                  label="Pending approvals"
                  value={String(dashboard.summary.pending_approvals)}
                  tone={dashboard.summary.pending_approvals ? "warning" : "positive"}
                  icon={BadgeCheck}
                  href="/approvals"
                />
                <StatTile
                  label="Opportunity value"
                  value={formatCurrency(dashboard.summary.opportunity_value, { compact: true })}
                  hint="Identified, not yet actioned"
                  icon={Lightbulb}
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
                <Card>
                  <CardHeader
                    title="Largest relationships"
                    description="Ranked by assets under advice."
                    action={
                      <Link href="/advisor/clients">
                        <Button variant="ghost" size="sm">
                          All clients <ChevronRight />
                        </Button>
                      </Link>
                    }
                  />
                  <Table>
                    <THead>
                      <TR>
                        <TH>Household</TH>
                        <TH>Segment</TH>
                        <TH align="right">Assets</TH>
                        <TH align="right">Net worth</TH>
                        <TH align="right">Attention</TH>
                      </TR>
                    </THead>
                    <tbody>
                      {dashboard.clients.slice(0, 8).map((client) => (
                        <TR key={client.household_id}>
                          <TD>
                            <Link href={`/advisor/clients/${client.household_id}`} className="font-medium text-ink hover:text-primary">
                              {client.name}
                            </Link>
                          </TD>
                          <TD>
                            <Badge tone="outline" size="sm">
                              {titleCase(client.segment)}
                            </Badge>
                          </TD>
                          <TD align="right" numeric className="font-medium">
                            {formatCurrency(client.total_assets, { compact: true })}
                          </TD>
                          <TD align="right" numeric>{formatCurrency(client.net_worth, { compact: true })}</TD>
                          <TD align="right">
                            <span className="flex justify-end gap-1.5">
                              {client.goals_off_track > 0 ? (
                                <Badge tone="warning" size="sm">{client.goals_off_track} goals</Badge>
                              ) : null}
                              {client.pending_approvals > 0 ? (
                                <Badge tone="info" size="sm">{client.pending_approvals} approvals</Badge>
                              ) : null}
                              {client.goals_off_track === 0 && client.pending_approvals === 0 ? (
                                <span className="text-ink-subtle">—</span>
                              ) : null}
                            </span>
                          </TD>
                        </TR>
                      ))}
                    </tbody>
                  </Table>
                </Card>

                <Card>
                  <CardHeader title="Service posture" description="Where the firm is carrying risk today." />
                  <CardBody>
                    <KeyValue
                      columns={1}
                      items={[
                        { label: "Open alerts", value: String(dashboard.summary.open_alerts) },
                        { label: "Open tasks", value: String(dashboard.summary.open_tasks) },
                        {
                          label: "Overdue tasks",
                          value: String(dashboard.summary.overdue_tasks),
                          hint: dashboard.summary.overdue_tasks ? "Past their due date" : undefined,
                        },
                        { label: "Goals off track", value: String(dashboard.summary.goals_off_track) },
                        { label: "Households", value: String(dashboard.summary.client_count) },
                        { label: "Institutional plans", value: String(plans.data?.length ?? 0) },
                      ]}
                    />
                  </CardBody>
                </Card>
              </div>
            </>
          );
        }}
      </DataState>

      {/* ------------------------------------------------ Approval pipeline */}
      <Section title="Approval pipeline" description="Every reviewable action in the firm, by state.">
        <DataState
          loading={approvals.loading}
          error={approvals.error}
          data={approvals.data}
          onRetry={approvals.refetch}
          loadingFallback={<LoadingGrid count={3} columns={3} />}
        >
          {(payload) => {
            const byStatus = payload.approvals.reduce<Record<string, number>>((counts, approval) => {
              counts[approval.status] = (counts[approval.status] ?? 0) + 1;
              return counts;
            }, {});
            const byType = payload.approvals.reduce<Record<string, number>>((counts, approval) => {
              counts[approval.entity_type] = (counts[approval.entity_type] ?? 0) + 1;
              return counts;
            }, {});

            const ORDER = ["draft", "submitted", "under_review", "approved", "completed", "rejected", "cancelled"];

            return (
              <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
                <Card>
                  <CardHeader
                    title="By state"
                    description={`${payload.total} requests · ${payload.pending_count} awaiting a decision`}
                  />
                  <CardBody className="space-y-2.5">
                    {ORDER.filter((status) => byStatus[status]).map((status) => (
                      <div key={status} className="flex items-center justify-between gap-4">
                        <StatusBadge status={status} />
                        <div className="flex flex-1 items-center gap-3">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                status === "approved" || status === "completed"
                                  ? "bg-positive"
                                  : status === "rejected" || status === "cancelled"
                                    ? "bg-negative"
                                    : "bg-primary",
                              )}
                              style={{ width: `${(byStatus[status] / Math.max(payload.approvals.length, 1)) * 100}%` }}
                            />
                          </div>
                          <span className="w-8 text-right text-sm font-medium tabular text-ink">{byStatus[status]}</span>
                        </div>
                      </div>
                    ))}
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="By request type" description="What the firm is actually deciding on." />
                  <CardBody>
                    <CategoryBars
                      data={Object.entries(byType).map(([type, count]) => ({ label: titleCase(type), value: count }))}
                      seriesLabel="Requests"
                      height={210}
                    />
                  </CardBody>
                </Card>
              </div>
            );
          }}
        </DataState>
      </Section>

      {/* -------------------------------------------------- Institutional */}
      <Section
        title="Institutional plans"
        actions={
          <Link href="/institutional/plans">
            <Button variant="ghost" size="sm">
              All plans <ChevronRight />
            </Button>
          </Link>
        }
      >
        <DataState
          loading={plans.loading}
          error={plans.error}
          data={plans.data}
          onRetry={plans.refetch}
          loadingFallback={<LoadingGrid count={2} columns={2} />}
          emptyWhen={(rows) => rows.length === 0}
          empty={
            <Card>
              <EmptyState icon={Building2} title="No plans under advisement" />
            </Card>
          }
        >
          {(rows) => (
            <Card>
              <Table>
                <THead>
                  <TR>
                    <TH>Plan</TH>
                    <TH align="right">Assets</TH>
                    <TH align="right">Participants</TH>
                    <TH align="right">Participation</TH>
                    <TH align="right"> </TH>
                  </TR>
                </THead>
                <tbody>
                  {rows.map((plan) => (
                    <TR key={plan.id}>
                      <TD className="font-medium">{plan.name}</TD>
                      <TD align="right" numeric>{formatCurrency(plan.total_assets, { compact: true })}</TD>
                      <TD align="right" numeric>{formatNumber(plan.participating_employees)}</TD>
                      <TD align="right" numeric>{formatPercent(plan.participation_rate, { decimals: 1 })}</TD>
                      <TD align="right">
                        <Link href={`/institutional?plan_id=${plan.id}`}>
                          <Button variant="ghost" size="icon-sm" aria-label={`Open ${plan.name}`}>
                            <ChevronRight />
                          </Button>
                        </Link>
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </Card>
          )}
        </DataState>
      </Section>

      {/* -------------------------------------------- Activity + platform */}
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader
            title="Recent activity"
            description="The most recent entries in the firm-wide audit trail."
            action={
              <Link href="/audit">
                <Button variant="ghost" size="sm">
                  Full trail <ChevronRight />
                </Button>
              </Link>
            }
          />
          <DataState
            loading={audit.loading}
            error={audit.error}
            data={audit.data}
            onRetry={audit.refetch}
            loadingFallback={<LoadingGrid count={2} columns={2} />}
            emptyWhen={(payload) => payload.events.length === 0}
            empty={<EmptyState icon={Activity} title="No activity recorded" />}
          >
            {(payload) => (
              <ul className="divide-y divide-border">
                {payload.events.map((event) => (
                  <li key={event.id} className="flex items-start gap-3 px-5 py-3">
                    <span
                      className={cn(
                        "mt-1.5 size-2 shrink-0 rounded-full",
                        event.status === "failed" ? "bg-negative" : "bg-primary",
                      )}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <p className="flex flex-wrap items-center gap-1.5">
                        <Badge tone={event.status === "failed" ? "negative" : "outline"} size="sm">
                          {titleCase(event.action)}
                        </Badge>
                        <span className="text-sm text-ink">{event.entity_label ?? titleCase(event.entity_type)}</span>
                      </p>
                      <p className="mt-0.5 text-xs text-ink-muted">
                        <span className="font-medium text-ink">{event.actor_name}</span>
                        {event.actor_role ? ` (${titleCase(event.actor_role)})` : ""} · {formatDateTime(event.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </DataState>
        </Card>

        <Card>
          <CardHeader
            title="Platform configuration"
            description="Which adapters are live in this environment."
            action={<Badge tone="outline">Read only</Badge>}
          />
          <DataState
            loading={health.loading}
            error={health.error}
            data={health.data}
            onRetry={health.refetch}
            loadingFallback={<LoadingGrid count={1} columns={1} />}
          >
            {(status) => (
              <CardBody className="space-y-4">
                <ul className="space-y-2.5">
                  <ConfigRow
                    icon={Database}
                    label="Database"
                    value={titleCase(status.database)}
                    tone={status.database === "unavailable" ? "negative" : "positive"}
                    note={status.seeded ? "Demonstration dataset loaded" : "No data seeded"}
                  />
                  <ConfigRow
                    icon={ShieldCheck}
                    label="Authentication"
                    value={titleCase(status.auth_provider)}
                    tone="positive"
                    note={
                      status.auth_provider === "supabase"
                        ? "Supabase Auth verifies access tokens"
                        : "Self-contained JWT auth against the users table"
                    }
                  />
                  <ConfigRow
                    icon={Cpu}
                    label="Intelligence layer"
                    value={`${titleCase(status.ai_provider)} · ${status.ai_mode}`}
                    tone={status.ai_mode === "live" ? "positive" : "primary"}
                    note={
                      status.ai_key_configured
                        ? "An API key is configured; narration runs over the deterministic engine"
                        : "No API key set — deterministic rules engine is serving every insight"
                    }
                  />
                  <ConfigRow
                    icon={ScrollText}
                    label="API"
                    value={API_URL.replace(/^https?:\/\//, "")}
                    tone="positive"
                    note={`Version ${status.version} · checked ${formatDateTime(status.timestamp)}`}
                  />
                </ul>

                <div className="rounded-md border border-border bg-surface-muted/60 px-3.5 py-3">
                  <p className="text-xs font-semibold text-ink">Financial integrity</p>
                  <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                    Every figure in this platform is produced by the deterministic calculation engine and published
                    with its method, as-of date, inputs, assumptions and limitations. The intelligence layer explains
                    those numbers; it never produces them.
                  </p>
                </div>
              </CardBody>
            )}
          </DataState>
        </Card>
      </div>
    </div>
  );
}

function ConfigRow({
  icon: Icon,
  label,
  value,
  tone,
  note,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone: "positive" | "primary" | "warning" | "negative";
  note?: string;
}) {
  return (
    <li className="flex items-start gap-3 rounded-md border border-border px-3.5 py-2.5">
      <Icon className="mt-0.5 size-4 shrink-0 text-ink-subtle" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-medium text-ink">{label}</span>
          <Badge tone={tone}>{value}</Badge>
        </div>
        {note ? <p className="mt-1 text-xs leading-relaxed text-ink-muted">{note}</p> : null}
      </div>
    </li>
  );
}
