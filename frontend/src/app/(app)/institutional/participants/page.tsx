"use client";

/** Participant roster (§29): balances, deferrals, vesting and engagement. */

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Search, Users } from "lucide-react";

import { formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardHeader, Input, Progress, Select, TD, TH, THead, TR, Table } from "@/components/ui";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingTable, NoResults } from "@/components/shared/states";

type Participant = {
  id: string;
  full_name: string;
  employee_id_masked: string;
  age: number;
  hire_date: string;
  years_of_service: number;
  annual_salary: number;
  deferral_rate: number;
  roth_deferral_rate: number;
  account_balance: number;
  roth_balance: number;
  employer_balance: number;
  vested_percentage: number;
  vested_balance: number;
  is_hce: boolean;
  is_auto_enrolled: boolean;
  has_beneficiary: boolean;
  retirement_age: number;
  status: string;
  engagement_score: number;
};

type ParticipantsPayload = {
  participants: Participant[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  plan: { id: string; name: string; participating_employees: number; eligible_employees: number };
};

export default function ParticipantsPage() {
  const { data: plans } = useApi<{ id: string; name: string }[]>("/api/plans");
  const [planId, setPlanId] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  const path = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "25" });
    if (planId) params.set("plan_id", planId);
    if (debounced) params.set("search", debounced);
    if (status) params.set("status_filter", status);
    return `/api/participants?${params.toString()}`;
  }, [planId, debounced, status, page]);

  const { data, error, loading, refetch } = useApi<ParticipantsPayload>(path);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Participants"
        description="A representative sample of the plan population, with balances, deferrals and vesting."
        actions={
          <Select
            value={planId}
            onChange={(event) => {
              setPlanId(event.target.value);
              setPage(1);
            }}
            className="h-9 w-64 text-xs"
            aria-label="Choose a plan"
          >
            <option value="">Default plan</option>
            {plans?.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name}
              </option>
            ))}
          </Select>
        }
      />

      {data ? (
        <StatRow columns={4}>
          <StatTile label="In this roster" value={formatNumber(data.total)} icon={Users} tone="primary" />
          <StatTile
            label="Average balance"
            value={formatCurrency(
              data.participants.reduce((total, row) => total + row.account_balance, 0) / Math.max(data.participants.length, 1),
              { compact: true },
            )}
            hint="On this page"
          />
          <StatTile
            label="Average deferral"
            value={formatPercent(
              data.participants.reduce((total, row) => total + row.deferral_rate + row.roth_deferral_rate, 0) /
                Math.max(data.participants.length, 1),
              { decimals: 1 },
            )}
            hint="On this page"
          />
          <StatTile
            label="Missing a beneficiary"
            value={String(data.participants.filter((row) => !row.has_beneficiary).length)}
            tone={data.participants.some((row) => !row.has_beneficiary) ? "warning" : "positive"}
            hint="On this page"
          />
        </StatRow>
      ) : null}

      <Card>
        <CardHeader
          title="Roster"
          description={data ? `Plan population ${formatNumber(data.plan.participating_employees)} of ${formatNumber(data.plan.eligible_employees)} eligible` : undefined}
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-subtle" aria-hidden />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search participants"
                  className="h-8 w-52 pl-8 text-xs"
                  aria-label="Search participants"
                />
              </div>
              <Select
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value);
                  setPage(1);
                }}
                className="h-8 w-36 text-xs"
                aria-label="Filter by status"
              >
                <option value="">Any status</option>
                <option value="active">Active</option>
                <option value="terminated">Terminated</option>
              </Select>
            </div>
          }
        />

        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={8} />}
          emptyWhen={(payload) => payload.participants.length === 0}
          empty={<NoResults query={debounced} onClear={() => setSearch("")} />}
        >
          {(payload) => (
            <>
              <Table>
                <THead>
                  <TR>
                    <TH>Participant</TH>
                    <TH align="right">Age</TH>
                    <TH align="right">Service</TH>
                    <TH align="right">Salary</TH>
                    <TH align="right">Deferral</TH>
                    <TH align="right">Balance</TH>
                    <TH align="right">Vested</TH>
                    <TH align="right">Engagement</TH>
                    <TH align="right">Flags</TH>
                  </TR>
                </THead>
                <tbody>
                  {payload.participants.map((participant) => (
                    <TR key={participant.id}>
                      <TD>
                        <span className="font-medium">{participant.full_name}</span>
                        <span className="mt-0.5 block text-xs text-ink-muted">
                          {participant.employee_id_masked} · hired {formatDate(participant.hire_date)}
                        </span>
                      </TD>
                      <TD align="right" numeric>{participant.age}</TD>
                      <TD align="right" numeric>{participant.years_of_service.toFixed(1)}y</TD>
                      <TD align="right" numeric>{formatCurrency(participant.annual_salary, { compact: true })}</TD>
                      <TD align="right" numeric>
                        {formatPercent(participant.deferral_rate + participant.roth_deferral_rate, { decimals: 1 })}
                        {participant.roth_deferral_rate > 0 ? (
                          <span className="mt-0.5 block text-2xs text-ink-subtle">
                            incl. {formatPercent(participant.roth_deferral_rate, { decimals: 1 })} Roth
                          </span>
                        ) : null}
                      </TD>
                      <TD align="right" numeric className="font-medium">{formatCurrency(participant.account_balance, { compact: true })}</TD>
                      <TD align="right">
                        <span className="tabular text-sm">{formatPercent(participant.vested_percentage, { decimals: 0 })}</span>
                        <Progress
                          value={participant.vested_percentage}
                          tone={participant.vested_percentage >= 1 ? "positive" : "warning"}
                          className="mt-1 w-16"
                        />
                      </TD>
                      <TD align="right" numeric className="text-ink-muted">
                        {formatPercent(participant.engagement_score, { decimals: 0 })}
                      </TD>
                      <TD align="right">
                        <span className="flex flex-wrap justify-end gap-1">
                          {participant.is_hce ? <Badge tone="outline" size="sm">HCE</Badge> : null}
                          {participant.is_auto_enrolled ? <Badge tone="outline" size="sm">Auto</Badge> : null}
                          {!participant.has_beneficiary ? <Badge tone="warning" size="sm">No beneficiary</Badge> : null}
                          {participant.status !== "active" ? <Badge tone="neutral" size="sm">Terminated</Badge> : null}
                        </span>
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>

              <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-3">
                <p className="text-xs text-ink-muted">
                  Page {payload.page} of {payload.pages} · {formatNumber(payload.total)} participants
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
