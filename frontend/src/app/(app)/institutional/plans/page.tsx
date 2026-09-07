"use client";

/** Plan directory: every plan the caller oversees. */

import Link from "next/link";
import { Building2, ChevronRight } from "lucide-react";

import { formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardHeader, TD, TH, THead, TR, Table } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type Plan = {
  id: string;
  name: string;
  plan_number: string;
  plan_type: string;
  sponsor: string;
  industry: string | null;
  plan_year_end: string;
  total_assets: number;
  eligible_employees: number;
  participating_employees: number;
  participation_rate: number;
  average_deferral_rate: number;
  employer_match_formula: string;
  vesting_schedule: string;
  auto_enrollment: boolean;
  recordkeeper: string;
  status: string;
};

export default function PlansPage() {
  const { data, error, loading, refetch } = useApi<Plan[]>("/api/plans");

  return (
    <div className="space-y-6">
      <PageHeader title="Plans" description="Retirement plans under advisement, with design and participation at a glance." />

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Plans" value={String(data.length)} icon={Building2} tone="primary" />
          <StatTile label="Combined assets" value={formatCurrency(data.reduce((total, plan) => total + plan.total_assets, 0), { compact: true })} />
          <StatTile label="Participants" value={formatNumber(data.reduce((total, plan) => total + plan.participating_employees, 0))} />
          <StatTile
            label="Average participation"
            value={formatPercent(
              data.reduce((total, plan) => total + plan.participation_rate, 0) / Math.max(data.length, 1),
              { decimals: 1 },
            )}
          />
        </StatRow>
      ) : null}

      <Card>
        <CardHeader title="Plan directory" />
        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={4} />}
          emptyWhen={(rows) => rows.length === 0}
          empty={<EmptyState icon={Building2} title="No plans available" />}
        >
          {(rows) => (
            <Table>
              <THead>
                <TR>
                  <TH>Plan</TH>
                  <TH>Sponsor</TH>
                  <TH align="right">Assets</TH>
                  <TH align="right">Participation</TH>
                  <TH align="right">Avg deferral</TH>
                  <TH>Match</TH>
                  <TH>Vesting</TH>
                  <TH>Plan year end</TH>
                  <TH align="right"> </TH>
                </TR>
              </THead>
              <tbody>
                {rows.map((plan) => (
                  <TR key={plan.id}>
                    <TD>
                      <span className="flex items-center gap-2 font-medium">
                        {plan.name}
                        <Badge tone="outline" size="sm">{plan.plan_type.toUpperCase()}</Badge>
                      </span>
                      <span className="mt-0.5 block text-xs text-ink-muted">
                        Plan {plan.plan_number} · {plan.recordkeeper}
                      </span>
                    </TD>
                    <TD className="text-xs">
                      {plan.sponsor}
                      {plan.industry ? <span className="mt-0.5 block text-2xs text-ink-subtle">{plan.industry}</span> : null}
                    </TD>
                    <TD align="right" numeric className="font-medium">{formatCurrency(plan.total_assets, { compact: true })}</TD>
                    <TD align="right" numeric>
                      {formatPercent(plan.participation_rate, { decimals: 1 })}
                      <span className="mt-0.5 block text-2xs text-ink-subtle">
                        {formatNumber(plan.participating_employees)} / {formatNumber(plan.eligible_employees)}
                      </span>
                    </TD>
                    <TD align="right" numeric>{formatPercent(plan.average_deferral_rate, { decimals: 1 })}</TD>
                    <TD className="max-w-[12rem] text-xs text-ink-muted">{plan.employer_match_formula}</TD>
                    <TD className="text-xs text-ink-muted">
                      {plan.vesting_schedule}
                      {plan.auto_enrollment ? <Badge tone="outline" size="sm" className="ml-1.5">Auto</Badge> : null}
                    </TD>
                    <TD className="whitespace-nowrap text-xs">{formatDate(plan.plan_year_end)}</TD>
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
          )}
        </DataState>
      </Card>
    </div>
  );
}
