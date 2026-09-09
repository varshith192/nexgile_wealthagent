"use client";

/** Philanthropy (§17): giving vehicles, grants, mission impact and deduction. */

import { HandCoins, HeartHandshake, PiggyBank, Target } from "lucide-react";

import { formatCurrency, formatDate, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardBody, CardHeader, Progress, TD, TH, THead, TR, Table } from "@/components/ui";
import { AllocationDonut } from "@/components/charts";
import { CalcDisclosure, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type PhilanthropyPayload = {
  as_of: string;
  summary: {
    total_balance: number;
    contributed_ytd: number;
    granted_ytd: number;
    annual_grant_target: number;
    grant_count: number;
    charities_supported: number;
  };
  vehicles: {
    id: string;
    name: string;
    vehicle_type: string;
    sponsor_organisation: string | null;
    balance: number;
    contributed_ytd: number;
    granted_ytd: number;
    annual_grant_target: number;
    payout_requirement: number | null;
    established_on: string | null;
    status: string;
    pacing: number;
  }[];
  grants: {
    id: string;
    charity: string;
    mission_area: string;
    location: string | null;
    amount: number;
    granted_on: string;
    purpose: string | null;
    is_recurring: boolean;
    status: string;
    impact_note: string | null;
  }[];
  mission_breakdown: { mission_area: string; amount: number }[];
  deduction_impact: Calculation<{
    total_donated: number;
    qualifying_limit: number;
    uncapped_deduction: number;
    capped_deduction: number;
    total_deduction: number;
    tax_saving: number;
    net_cost_of_giving: number;
    deduction_rate: number;
    capped_donations_disallowed: number;
  }>;
  giving_plans: {
    id: string;
    name: string;
    tax_year: number;
    target_amount: number;
    committed_amount: number;
    progress: number;
    mission_focus: string;
    strategy: string;
    status: string;
    review_date: string | null;
  }[];
};

export default function PhilanthropyPage() {
  const { data, error, loading, refetch } = useApi<PhilanthropyPayload>("/api/philanthropy");

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(giving) => {
          const summary = giving.summary;
          const deduction = giving.deduction_impact.result;
          const totalMission = giving.mission_breakdown.reduce((total, row) => total + row.amount, 0) || 1;

          return (
            <>
              <PageHeader
                title="Philanthropy"
                description="Charitable vehicles, grant activity and the tax impact of how you give."
                meta={<span className="text-xs text-ink-muted">As of {formatDate(giving.as_of)}</span>}
              />

              <StatRow columns={4}>
                <StatTile
                  label="Charitable balance"
                  value={formatCurrency(summary.total_balance, { compact: true })}
                  hint={`${giving.vehicles.length} vehicle${giving.vehicles.length === 1 ? "" : "s"}`}
                  icon={HandCoins}
                  tone="primary"
                />
                <StatTile
                  label="Granted this year"
                  value={formatCurrency(summary.granted_ytd, { compact: true })}
                  hint={`Target ${formatCurrency(summary.annual_grant_target, { compact: true })}`}
                  icon={Target}
                  tone={summary.granted_ytd < summary.annual_grant_target ? "warning" : "positive"}
                />
                <StatTile
                  label="Charities supported"
                  value={String(summary.charities_supported)}
                  hint={`${summary.grant_count} grants made`}
                  icon={HeartHandshake}
                />
                <StatTile
                  label="Section 80G tax saving"
                  value={formatCurrency(deduction.tax_saving, { compact: true })}
                  hint={`${formatCurrency(deduction.total_deduction, { compact: true })} deduction claimed`}
                  icon={PiggyBank}
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
                <Card>
                  <CardHeader title="Giving vehicles" description="Private foundations and charitable trusts. India has no donor-advised fund structure." />
                  {giving.vehicles.length === 0 ? (
                    <EmptyState title="No charitable vehicles" description="A private foundation or charitable trust would appear here." />
                  ) : (
                    <ul className="divide-y divide-border">
                      {giving.vehicles.map((vehicle) => (
                        <li key={vehicle.id} className="px-5 py-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                                {vehicle.name}
                                <Badge tone="outline" size="sm">{titleCase(vehicle.vehicle_type)}</Badge>
                                <StatusBadge status={vehicle.status} />
                              </p>
                              {vehicle.sponsor_organisation ? (
                                <p className="mt-0.5 text-xs text-ink-muted">Sponsored by {vehicle.sponsor_organisation}</p>
                              ) : null}
                            </div>
                            <p className="shrink-0 text-lg font-semibold tabular text-ink">
                              {formatCurrency(vehicle.balance, { compact: true })}
                            </p>
                          </div>

                          <div className="mt-3">
                            <div className="flex items-baseline justify-between text-xs">
                              <span className="text-ink-muted">Granting against target</span>
                              <span className="tabular text-ink">
                                {formatCurrency(vehicle.granted_ytd, { compact: true })} of{" "}
                                {formatCurrency(vehicle.annual_grant_target, { compact: true })}
                              </span>
                            </div>
                            <Progress
                              value={vehicle.pacing}
                              tone={vehicle.pacing >= 0.75 ? "positive" : vehicle.pacing >= 0.4 ? "warning" : "negative"}
                              className="mt-1.5"
                              showTrackLabel
                            />
                          </div>

                          <KeyValue
                            className="mt-3.5"
                            columns={3}
                            items={[
                              { label: "Contributed this year", value: formatCurrency(vehicle.contributed_ytd, { compact: true }) },
                              {
                                label: "Payout requirement",
                                value: vehicle.payout_requirement ? formatPercent(vehicle.payout_requirement, { decimals: 0 }) : "None",
                              },
                              { label: "Established", value: vehicle.established_on ? formatDate(vehicle.established_on) : "—" },
                            ]}
                          />
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                <Card>
                  <CardHeader title="Where the money goes" description="Grants by mission area." />
                  <CardBody>
                    {giving.mission_breakdown.length === 0 ? (
                      <EmptyState title="No grants recorded yet" />
                    ) : (
                      <AllocationDonut
                        data={giving.mission_breakdown.map((row) => ({
                          label: row.mission_area,
                          value: row.amount,
                          weight: row.amount / totalMission,
                        }))}
                        height={210}
                        centerLabel="Granted"
                        centerValue={formatCurrency(totalMission, { compact: true })}
                      />
                    )}
                  </CardBody>
                </Card>
              </div>

              <Card>
                <CardHeader title="Deduction impact" description="The tax value of this year's giving, and what it actually costs." />
                <CardBody className="space-y-4">
                  <KeyValue
                    columns={3}
                    items={[
                      { label: "Total donated", value: formatCurrency(deduction.total_donated, { compact: true }) },
                      { label: "Qualifying limit", value: formatCurrency(deduction.qualifying_limit, { compact: true }) },
                      { label: "Uncapped deduction", value: formatCurrency(deduction.uncapped_deduction, { compact: true }) },
                      { label: "Capped deduction", value: formatCurrency(deduction.capped_deduction, { compact: true }) },
                      { label: "Total deduction", value: formatCurrency(deduction.total_deduction, { compact: true }) },
                      { label: "Deduction rate", value: formatPercent(deduction.deduction_rate, { decimals: 1 }) },
                      { label: "Tax saving", value: formatCurrency(deduction.tax_saving, { compact: true }) },
                      { label: "Capped donations disallowed", value: formatCurrency(deduction.capped_donations_disallowed, { compact: true }) },
                      { label: "Net cost of giving", value: formatCurrency(deduction.net_cost_of_giving, { compact: true }) },
                    ]}
                  />
                  <CalcDisclosure calculation={giving.deduction_impact} />
                </CardBody>
              </Card>

              <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
                <Card>
                  <CardHeader title="Grant history" description={`${giving.grants.length} grants recorded.`} />
                  {giving.grants.length === 0 ? (
                    <EmptyState title="No grants yet" />
                  ) : (
                    <Table>
                      <THead>
                        <TR>
                          <TH>Charity</TH>
                          <TH>Mission</TH>
                          <TH>Granted</TH>
                          <TH align="right">Amount</TH>
                          <TH align="right">Status</TH>
                        </TR>
                      </THead>
                      <tbody>
                        {giving.grants.map((grant) => (
                          <TR key={grant.id}>
                            <TD>
                              <span className="flex items-center gap-2 font-medium">
                                {grant.charity}
                                {grant.is_recurring ? <Badge tone="outline" size="sm">Recurring</Badge> : null}
                              </span>
                              {grant.impact_note ? (
                                <span className="mt-0.5 block max-w-[22rem] text-xs text-ink-muted">{grant.impact_note}</span>
                              ) : null}
                            </TD>
                            <TD className="text-xs">
                              {grant.mission_area}
                              {grant.location ? <span className="mt-0.5 block text-2xs text-ink-subtle">{grant.location}</span> : null}
                            </TD>
                            <TD className="whitespace-nowrap text-xs">{formatDate(grant.granted_on)}</TD>
                            <TD align="right" numeric className="font-medium">{formatCurrency(grant.amount)}</TD>
                            <TD align="right"><StatusBadge status={grant.status} /></TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card>

                <div className="space-y-6">
                  <Card>
                    <CardHeader title="Giving plans" />
                    {giving.giving_plans.length === 0 ? (
                      <EmptyState title="No giving plan set" />
                    ) : (
                      <ul className="divide-y divide-border">
                        {giving.giving_plans.map((plan) => (
                          <li key={plan.id} className="px-5 py-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-ink">{plan.name}</p>
                                <p className="mt-0.5 text-xs text-ink-muted">{plan.strategy}</p>
                              </div>
                              <StatusBadge status={plan.status} />
                            </div>
                            <Progress value={plan.progress} tone="primary" className="mt-3" showTrackLabel />
                            <p className="mt-2 text-xs text-ink-muted">
                              {formatCurrency(plan.committed_amount, { compact: true })} committed of{" "}
                              {formatCurrency(plan.target_amount, { compact: true })} · focus {plan.mission_focus}
                              {plan.review_date ? ` · review ${formatDate(plan.review_date)}` : ""}
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </Card>
                </div>
              </div>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
