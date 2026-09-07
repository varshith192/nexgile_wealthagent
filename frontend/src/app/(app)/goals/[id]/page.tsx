"use client";

/** Goal detail with scenario comparison (§14). Scenarios never alter records. */

import { use, useState } from "react";
import { Info, Play, Wallet } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Progress, TD, TH, THead, TR, Table } from "@/components/ui";
import { CategoryBars } from "@/components/charts";
import { CalcDisclosure, GoalStatusBadge, ProjectionNotice } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

type ProjectionResult = {
  projected_value: number;
  inflation_adjusted_target: number;
  gap: number;
  funded_ratio: number;
  progress_percent: number;
  status: string;
  required_monthly_contribution: number;
  additional_monthly_needed: number;
  months_to_target: number;
  years_to_target: number;
};

type GoalDetailPayload = {
  goal: {
    id: string;
    name: string;
    goal_type: string;
    description: string | null;
    target_amount: number;
    current_amount: number;
    target_date: string;
    monthly_contribution: number;
    expected_return: number;
    inflation_rate: number;
    priority: string;
    status: string;
    owner_label: string | null;
  };
  projection: Calculation<ProjectionResult>;
  linked_accounts: {
    id: string;
    name: string;
    account_type: string;
    balance: number;
    allocation_percent: number;
    contribution_to_goal: number;
  }[];
  saved_scenarios: { id: string; name: string; scenario_key: string; run_at: string | null }[];
};

type ScenarioRow = {
  key: string;
  label: string;
  description: string;
  is_baseline: boolean;
  projected_value: number;
  gap: number;
  funded_ratio: number;
  status: string;
  target_date: string;
  monthly_contribution: number;
  expected_return: number;
  delta_vs_base: number;
  assumptions: string[];
};

type ScenarioPayload = Calculation<{ base: ProjectionResult; scenarios: ScenarioRow[] }>;

export default function GoalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, loading, refetch } = useApi<GoalDetailPayload>(`/api/goals/${id}`);
  const [scenarios, setScenarios] = useState<ScenarioPayload | null>(null);

  const { run: runScenarios, pending } = useMutation(async () => {
    const result = await api.post<ScenarioPayload>(`/api/goals/${id}/scenarios`, { persist: true });
    setScenarios(result);
    refetch();
    return result;
  });

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(payload) => {
          const goal = payload.goal;
          const projection = payload.projection.result;
          const tone =
            projection.status === "on_track"
              ? "positive"
              : projection.status === "off_track"
                ? "negative"
                : projection.status === "at_risk"
                  ? "warning"
                  : "primary";

          return (
            <>
              <PageHeader
                breadcrumb={[{ label: "Goals", href: "/goals" }, { label: goal.name }]}
                title={goal.name}
                description={goal.description ?? undefined}
                meta={
                  <>
                    <Badge tone="outline">{titleCase(goal.goal_type)}</Badge>
                    <Badge tone="outline">{titleCase(goal.priority)} priority</Badge>
                    {goal.owner_label ? <Badge tone="outline">{goal.owner_label}</Badge> : null}
                    <GoalStatusBadge status={projection.status} />
                    <span className="text-xs text-ink-muted">
                      Target {formatDate(goal.target_date, "long")} · {projection.years_to_target} years away
                    </span>
                  </>
                }
                actions={
                  <Button variant="primary" size="sm" loading={pending} onClick={() => runScenarios()}>
                    <Play />
                    Run scenarios
                  </Button>
                }
              />

              <StatRow columns={4}>
                <StatTile
                  label="Currently funded"
                  value={formatCurrency(goal.current_amount, { compact: true })}
                  hint={`${formatPercent(projection.progress_percent, { decimals: 0 })} of the target`}
                  tone="primary"
                />
                <StatTile
                  label="Projected at target date"
                  value={formatCurrency(projection.projected_value, { compact: true })}
                  hint={`Against ${formatCurrency(projection.inflation_adjusted_target, { compact: true })} inflation-adjusted`}
                />
                <StatTile
                  label={projection.gap >= 0 ? "Projected surplus" : "Projected shortfall"}
                  value={formatCurrency(Math.abs(projection.gap), { compact: true })}
                  tone={projection.gap >= 0 ? "positive" : "negative"}
                  hint={`Funded ratio ${formatPercent(projection.funded_ratio, { decimals: 0 })}`}
                />
                <StatTile
                  label="Monthly contribution"
                  value={formatCurrency(goal.monthly_contribution)}
                  hint={
                    projection.additional_monthly_needed > 0
                      ? `${formatCurrency(projection.additional_monthly_needed)} more closes the gap`
                      : "Sufficient on current assumptions"
                  }
                  tone={projection.additional_monthly_needed > 0 ? "warning" : "positive"}
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
                <Card>
                  <CardHeader title="Funding progress" description="Where this goal stands today, and where the plan takes it." />
                  <CardBody className="space-y-5">
                    <div>
                      <div className="flex items-baseline justify-between">
                        <span className="text-2xl font-semibold tabular text-ink">
                          {formatCurrency(goal.current_amount)}
                        </span>
                        <span className="text-sm text-ink-muted">of {formatCurrency(goal.target_amount)}</span>
                      </div>
                      <Progress value={projection.progress_percent} tone={tone} className="mt-3" showTrackLabel />
                    </div>

                    <KeyValue
                      items={[
                        { label: "Target amount (today's dollars)", value: formatCurrency(goal.target_amount) },
                        { label: "Target adjusted for inflation", value: formatCurrency(projection.inflation_adjusted_target) },
                        { label: "Expected annual return", value: formatPercent(goal.expected_return, { decimals: 2 }) },
                        { label: "Inflation assumption", value: formatPercent(goal.inflation_rate, { decimals: 2 }) },
                        { label: "Months to target", value: String(projection.months_to_target) },
                        { label: "Required monthly contribution", value: formatCurrency(projection.required_monthly_contribution) },
                      ]}
                    />

                    <ProjectionNotice />
                    <CalcDisclosure calculation={payload.projection} />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="Funding sources" description="Accounts linked to this goal." />
                  {payload.linked_accounts.length === 0 ? (
                    <CardBody>
                      <p className="text-sm text-ink-muted">
                        No accounts are linked to this goal yet, so the balance is tracked manually.
                      </p>
                    </CardBody>
                  ) : (
                    <ul className="divide-y divide-border">
                      {payload.linked_accounts.map((account) => (
                        <li key={account.id} className="flex items-center justify-between gap-3 px-5 py-3.5">
                          <div className="min-w-0">
                            <p className="flex items-center gap-2 text-sm font-medium text-ink">
                              <Wallet className="size-3.5 text-ink-subtle" aria-hidden />
                              {account.name}
                            </p>
                            <p className="mt-0.5 text-xs text-ink-muted">
                              {titleCase(account.account_type)} · {formatPercent(account.allocation_percent, { decimals: 0 })} allocated
                            </p>
                          </div>
                          <div className="shrink-0 text-right">
                            <p className="text-sm font-medium tabular text-ink">
                              {formatCurrency(account.contribution_to_goal, { compact: true })}
                            </p>
                            <p className="mt-0.5 text-xs tabular text-ink-subtle">
                              of {formatCurrency(account.balance, { compact: true })}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>

              {/* ----------------------------------------------- Scenarios */}
              <Card>
                <CardHeader
                  title="Scenario comparison"
                  description="Each scenario changes one input and re-runs the same projection. Nothing here is saved to your plan."
                  action={
                    <Button size="sm" loading={pending} onClick={() => runScenarios()}>
                      <Play />
                      {scenarios ? "Re-run" : "Run scenarios"}
                    </Button>
                  }
                />

                {!scenarios ? (
                  <CardBody>
                    <div className="rounded-md border border-dashed border-border px-5 py-10 text-center">
                      <p className="text-sm font-medium text-ink">Compare what-ifs side by side</p>
                      <p className="mx-auto mt-1.5 max-w-md text-sm leading-6 text-ink-muted">
                        Base case, higher savings, lower return and an earlier target date — each recalculated from
                        the same engine that produced the figures above.
                      </p>
                      <Button variant="primary" size="sm" className="mt-5" loading={pending} onClick={() => runScenarios()}>
                        <Play />
                        Run scenarios
                      </Button>
                    </div>
                  </CardBody>
                ) : (
                  <CardBody className="space-y-6">
                    <CategoryBars
                      data={scenarios.result.scenarios.map((row) => ({ label: row.label, value: row.projected_value }))}
                      seriesLabel="Projected value at target date"
                      formatValue={(value) => formatCurrency(value, { compact: true })}
                      height={230}
                    />

                    <div className="scroll-x rounded-md border border-border">
                      <Table>
                        <THead>
                          <TR>
                            <TH>Scenario</TH>
                            <TH align="right">Contribution</TH>
                            <TH align="right">Return</TH>
                            <TH>Target date</TH>
                            <TH align="right">Projected</TH>
                            <TH align="right">vs base</TH>
                            <TH align="right">Funded</TH>
                            <TH align="right">Status</TH>
                          </TR>
                        </THead>
                        <tbody>
                          {scenarios.result.scenarios.map((row) => (
                            <TR key={row.key} className={row.is_baseline ? "bg-surface-muted/60" : undefined}>
                              <TD>
                                <span className="flex items-center gap-2 font-medium">
                                  {row.label}
                                  {row.is_baseline ? <Badge tone="outline" size="sm">Base</Badge> : null}
                                </span>
                                <span className="mt-0.5 block text-xs text-ink-muted">{row.description}</span>
                              </TD>
                              <TD align="right" numeric>{formatCurrency(row.monthly_contribution)}</TD>
                              <TD align="right" numeric>{formatPercent(row.expected_return, { decimals: 2 })}</TD>
                              <TD className="whitespace-nowrap text-xs">{formatDate(row.target_date)}</TD>
                              <TD align="right" numeric className="font-medium">
                                {formatCurrency(row.projected_value, { compact: true })}
                              </TD>
                              <TD
                                align="right"
                                numeric
                                className={cn(
                                  row.is_baseline ? "text-ink-subtle" : row.delta_vs_base >= 0 ? "text-positive" : "text-negative",
                                )}
                              >
                                {row.is_baseline ? "—" : formatCurrency(row.delta_vs_base, { compact: true, signed: true })}
                              </TD>
                              <TD align="right" numeric>{formatPercent(row.funded_ratio, { decimals: 0 })}</TD>
                              <TD align="right">
                                <GoalStatusBadge status={row.status} />
                              </TD>
                            </TR>
                          ))}
                        </tbody>
                      </Table>
                    </div>

                    <div className="flex items-start gap-2 rounded-md border border-info/25 bg-info-soft px-3.5 py-3 text-xs leading-relaxed text-ink-muted">
                      <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden />
                      <span>
                        Scenarios are read-only projections. Running them does not change your goal, your accounts or
                        any other record — the run is written to the audit trail as a scenario, not a change.
                      </span>
                    </div>

                    <CalcDisclosure calculation={scenarios} label="How scenarios are calculated" />
                  </CardBody>
                )}
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
