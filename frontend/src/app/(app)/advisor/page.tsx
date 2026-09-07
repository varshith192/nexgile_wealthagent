"use client";

/** Advisor workstation (§20): the book, what needs a decision, and what is due. */

import Link from "next/link";
import {
  AlertTriangle,
  BadgeCheck,
  CalendarDays,
  ChevronRight,
  CircleDollarSign,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

import { formatCurrency, formatDate, formatDateTime, formatPercent, titleCase } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardHeader, TD, TH, THead, TR, Table } from "@/components/ui";
import { SeverityBadge, StatusBadge } from "@/components/shared/indicators";
import { PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type AdvisorDashboard = {
  advisor: { id: string; name: string; title: string | null; role: string };
  summary: {
    client_count: number;
    household_count: number;
    total_aum: number;
    average_relationship: number;
    pending_approvals: number;
    open_alerts: number;
    meetings_this_week: number;
    open_tasks: number;
    overdue_tasks: number;
    goals_off_track: number;
    opportunity_value: number;
  };
  clients: {
    household_id: string;
    name: string;
    segment: string;
    primary_contact: string;
    total_assets: number;
    net_worth: number;
    account_count: number;
    goal_count: number;
    goals_off_track: number;
    pending_approvals: number;
    next_meeting: string | null;
    status: string;
  }[];
  pending_approvals: {
    id: string;
    title: string;
    entity_type: string;
    status: string;
    priority: string;
    household: string;
    household_id: string;
    estimated_impact: number | null;
    submitted_at: string | null;
    due_date: string | null;
  }[];
  meetings: { id: string; title: string; household: string; household_id: string; starts_at: string; meeting_type: string; location: string }[];
  tasks: {
    id: string;
    title: string;
    category: string;
    priority: string;
    status: string;
    due_date: string | null;
    household: string;
    household_id: string;
    is_overdue: boolean;
  }[];
  alerts: { id: string; title: string; body: string; severity: string; category: string; household: string; household_id: string; created_at: string }[];
  opportunities: {
    id: string;
    title: string;
    opportunity_type: string;
    estimated_benefit: number;
    household: string;
    household_id: string;
    severity: string;
    deadline: string | null;
  }[];
};

export default function AdvisorPage() {
  const { data, error, loading, refetch } = useApi<AdvisorDashboard>("/api/advisor");

  return (
    <div className="space-y-8">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(dashboard) => (
          <>
            <PageHeader
              title="Advisor workstation"
              description={`${dashboard.advisor.name}${dashboard.advisor.title ? ` · ${dashboard.advisor.title}` : ""}`}
              actions={
                <>
                  <Link href="/advisor/clients">
                    <Button size="sm">
                      <Users />
                      All clients
                    </Button>
                  </Link>
                  <Link href="/approvals">
                    <Button variant="primary" size="sm">
                      <BadgeCheck />
                      Approvals ({dashboard.summary.pending_approvals})
                    </Button>
                  </Link>
                </>
              }
            />

            <StatRow columns={5}>
              <StatTile
                label="Assets under advice"
                value={formatCurrency(dashboard.summary.total_aum, { compact: true })}
                hint={`${dashboard.summary.client_count} households`}
                icon={TrendingUp}
                tone="primary"
              />
              <StatTile
                label="Average relationship"
                value={formatCurrency(dashboard.summary.average_relationship, { compact: true })}
                icon={Users}
                href="/advisor/clients"
              />
              <StatTile
                label="Pending approvals"
                value={String(dashboard.summary.pending_approvals)}
                tone={dashboard.summary.pending_approvals ? "warning" : "positive"}
                icon={BadgeCheck}
                href="/approvals"
              />
              <StatTile
                label="Goals off track"
                value={String(dashboard.summary.goals_off_track)}
                tone={dashboard.summary.goals_off_track ? "warning" : "positive"}
                icon={Target}
              />
              <StatTile
                label="Opportunity value"
                value={formatCurrency(dashboard.summary.opportunity_value, { compact: true })}
                hint="Identified tax opportunities"
                icon={CircleDollarSign}
              />
            </StatRow>

            <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
              <Card>
                <CardHeader
                  title="Awaiting your decision"
                  description="Requests submitted for review across your book."
                  action={
                    <Link href="/approvals">
                      <Button variant="ghost" size="sm">
                        All approvals <ChevronRight />
                      </Button>
                    </Link>
                  }
                />
                {dashboard.pending_approvals.length === 0 ? (
                  <EmptyState icon={BadgeCheck} title="Nothing awaiting a decision" description="Your approval queue is clear." />
                ) : (
                  <ul className="divide-y divide-border">
                    {dashboard.pending_approvals.map((approval) => (
                      <li key={approval.id}>
                        <Link href="/approvals" className="flex items-start justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-surface-muted/70">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <StatusBadge status={approval.status} />
                              <Badge tone="outline" size="sm">{titleCase(approval.entity_type)}</Badge>
                              {approval.priority === "high" ? <Badge tone="warning" size="sm">High priority</Badge> : null}
                            </div>
                            <p className="mt-1.5 text-sm font-medium text-ink">{approval.title}</p>
                            <p className="mt-0.5 text-xs text-ink-muted">
                              {approval.household}
                              {approval.submitted_at ? ` · submitted ${formatDate(approval.submitted_at)}` : ""}
                              {approval.due_date ? ` · due ${formatDate(approval.due_date)}` : ""}
                            </p>
                          </div>
                          {approval.estimated_impact !== null ? (
                            <p className="shrink-0 text-right text-sm font-semibold tabular text-ink">
                              {formatCurrency(approval.estimated_impact, { compact: true })}
                            </p>
                          ) : null}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <CardHeader title="Alerts across the book" description="Highest severity first." />
                {dashboard.alerts.length === 0 ? (
                  <EmptyState title="No open alerts" />
                ) : (
                  <ul className="divide-y divide-border">
                    {dashboard.alerts.slice(0, 7).map((alert) => (
                      <li key={alert.id} className="px-5 py-3">
                        <div className="flex items-start gap-2.5">
                          <SeverityBadge severity={alert.severity as "low" | "medium" | "high"} />
                          <div className="min-w-0">
                            <p className="text-sm font-medium leading-5 text-ink">{alert.title}</p>
                            <p className="mt-0.5 text-xs leading-5 text-ink-muted">{alert.body}</p>
                            <Link
                              href={`/advisor/clients/${alert.household_id}`}
                              className="mt-1 inline-block text-2xs font-medium text-primary hover:underline"
                            >
                              {alert.household}
                            </Link>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            <Section
              title="Book of business"
              description={`${dashboard.clients.length} households`}
              actions={
                <Link href="/advisor/clients">
                  <Button variant="ghost" size="sm">
                    View all <ChevronRight />
                  </Button>
                </Link>
              }
            >
              <Card>
                <Table>
                  <THead>
                    <TR>
                      <TH>Household</TH>
                      <TH align="right">Assets</TH>
                      <TH align="right">Net worth</TH>
                      <TH align="right">Accounts</TH>
                      <TH align="right">Goals</TH>
                      <TH align="right">Approvals</TH>
                      <TH>Next meeting</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {dashboard.clients.map((client) => (
                      <TR key={client.household_id} className="cursor-pointer">
                        <TD>
                          <Link href={`/advisor/clients/${client.household_id}`} className="block">
                            <span className="font-medium text-ink hover:text-primary">{client.name}</span>
                            <span className="mt-0.5 block text-xs text-ink-muted">
                              {client.primary_contact} · {titleCase(client.segment)}
                            </span>
                          </Link>
                        </TD>
                        <TD align="right" numeric className="font-medium">{formatCurrency(client.total_assets, { compact: true })}</TD>
                        <TD align="right" numeric>{formatCurrency(client.net_worth, { compact: true })}</TD>
                        <TD align="right" numeric className="text-ink-muted">{client.account_count}</TD>
                        <TD align="right">
                          <span className="tabular">{client.goal_count}</span>
                          {client.goals_off_track > 0 ? (
                            <Badge tone="warning" size="sm" className="ml-1.5">
                              {client.goals_off_track} off track
                            </Badge>
                          ) : null}
                        </TD>
                        <TD align="right">
                          {client.pending_approvals > 0 ? (
                            <Badge tone="warning" size="sm">{client.pending_approvals}</Badge>
                          ) : (
                            <span className="text-ink-subtle">—</span>
                          )}
                        </TD>
                        <TD className="whitespace-nowrap text-xs text-ink-muted">
                          {client.next_meeting ? formatDate(client.next_meeting) : "Not scheduled"}
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </Card>
            </Section>

            <div className="grid gap-6 xl:grid-cols-3">
              <Card>
                <CardHeader title="Upcoming meetings" description={`${dashboard.summary.meetings_this_week} within seven days`} />
                {dashboard.meetings.length === 0 ? (
                  <EmptyState icon={CalendarDays} title="Nothing scheduled" />
                ) : (
                  <ul className="divide-y divide-border">
                    {dashboard.meetings.slice(0, 6).map((meeting) => (
                      <li key={meeting.id} className="px-5 py-3">
                        <p className="text-sm font-medium text-ink">{meeting.title}</p>
                        <p className="mt-0.5 text-xs text-ink-muted">
                          {meeting.household} · {formatDateTime(meeting.starts_at)}
                        </p>
                        <p className="mt-0.5 text-2xs text-ink-subtle">{meeting.location}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <CardHeader
                  title="Tasks"
                  description={`${dashboard.summary.open_tasks} open · ${dashboard.summary.overdue_tasks} overdue`}
                  action={
                    <Link href="/advisor/tasks">
                      <Button variant="ghost" size="sm">
                        All <ChevronRight />
                      </Button>
                    </Link>
                  }
                />
                {dashboard.tasks.length === 0 ? (
                  <EmptyState title="No open tasks" />
                ) : (
                  <ul className="divide-y divide-border">
                    {dashboard.tasks.slice(0, 6).map((task) => (
                      <li key={task.id} className="px-5 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className={cn("text-sm font-medium leading-5", task.is_overdue ? "text-negative" : "text-ink")}>
                              {task.title}
                            </p>
                            <p className="mt-0.5 text-xs text-ink-muted">
                              {task.household}
                              {task.due_date ? ` · due ${formatDate(task.due_date)}` : ""}
                            </p>
                          </div>
                          {task.is_overdue ? (
                            <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-negative" aria-hidden />
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card>
                <CardHeader
                  title="Opportunities"
                  description="Identified tax opportunities across the book."
                  action={
                    <Link href="/advisor/tax">
                      <Button variant="ghost" size="sm">
                        Tax <ChevronRight />
                      </Button>
                    </Link>
                  }
                />
                {dashboard.opportunities.length === 0 ? (
                  <EmptyState title="No open opportunities" />
                ) : (
                  <ul className="divide-y divide-border">
                    {dashboard.opportunities.slice(0, 6).map((opportunity) => (
                      <li key={opportunity.id} className="px-5 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium leading-5 text-ink">{opportunity.title}</p>
                            <p className="mt-0.5 text-xs text-ink-muted">
                              {opportunity.household}
                              {opportunity.deadline ? ` · by ${formatDate(opportunity.deadline)}` : ""}
                            </p>
                          </div>
                          <p className="shrink-0 text-sm font-semibold tabular text-positive">
                            {formatCurrency(opportunity.estimated_benefit, { compact: true })}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </>
        )}
      </DataState>
    </div>
  );
}
