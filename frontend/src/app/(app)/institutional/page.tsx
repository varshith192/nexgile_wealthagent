"use client";

/** Plan sponsor dashboard (§29): plan health, engagement and design. */

import { useState } from "react";
import Link from "next/link";
import { Building2, ChevronRight, PiggyBank, TrendingUp, Users } from "lucide-react";

import { formatCurrency, formatDate, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, Progress, Select } from "@/components/ui";
import { CategoryBars } from "@/components/charts";
import { CalcDisclosure, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

type SponsorDashboard = {
  plan: {
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
    auto_enrollment_rate: number;
    auto_escalation: boolean;
    auto_escalation_cap: number;
    loans_allowed: boolean;
    hardship_allowed: boolean;
    recordkeeper: string;
    status: string;
  };
  as_of: string;
  health: Calculation<{
    score: number;
    grade: string;
    participation_rate: number;
    components: Record<string, { value: number; weight: number; score: number }>;
  }>;
  metrics: {
    total_assets: number;
    participant_count: number;
    active_participants: number;
    average_balance: number;
    median_balance: number;
    average_deferral_rate: number;
    roth_adoption: number;
    employer_contributions_ytd: number;
    employee_contributions_ytd: number;
    loans_outstanding: number;
    loan_balance: number;
    hardship_count: number;
    beneficiary_coverage: number;
    auto_enrolled: number;
    average_engagement: number;
    hce_count: number;
    fully_vested: number;
  };
  vesting_distribution: { bucket: string; count: number }[];
  deferral_distribution: { bucket: string; count: number }[];
  compliance_summary: { counts: Record<string, number>; next_deadline: string | null };
};

const GRADE_TONE: Record<string, "positive" | "warning" | "negative" | "primary"> = {
  strong: "positive",
  healthy: "primary",
  needs_attention: "warning",
  at_risk: "negative",
};

export default function InstitutionalPage() {
  const { data: plans } = useApi<{ id: string; name: string }[]>("/api/plans");
  const [planId, setPlanId] = useState("");
  const suffix = planId ? `?plan_id=${planId}` : "";
  const { data, error, loading, refetch } = useApi<SponsorDashboard>(`/api/institutional${suffix}`, [planId]);

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(dashboard) => {
          const plan = dashboard.plan;
          const metrics = dashboard.metrics;
          const health = dashboard.health.result;

          return (
            <>
              <PageHeader
                title={plan.name}
                description={`${plan.sponsor}${plan.industry ? ` · ${plan.industry}` : ""} · recordkept by ${plan.recordkeeper}`}
                meta={
                  <>
                    <Badge tone="outline">{plan.plan_type.toUpperCase()}</Badge>
                    <Badge tone="outline">Plan {plan.plan_number}</Badge>
                    <StatusBadge status={plan.status} />
                    <span className="text-xs text-ink-muted">
                      Plan year ends {formatDate(plan.plan_year_end)} · as of {formatDate(dashboard.as_of)}
                    </span>
                  </>
                }
                actions={
                  <Select
                    value={planId}
                    onChange={(event) => setPlanId(event.target.value)}
                    className="h-9 w-64 text-xs"
                    aria-label="Choose a plan"
                  >
                    <option value="">Default plan</option>
                    {plans?.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.name}
                      </option>
                    ))}
                  </Select>
                }
              />

              <StatRow columns={5}>
                <StatTile label="Plan assets" value={formatCurrency(metrics.total_assets, { compact: true })} icon={TrendingUp} tone="primary" />
                <StatTile
                  label="Participation"
                  value={formatPercent(plan.participation_rate, { decimals: 1 })}
                  hint={`${formatNumber(plan.participating_employees)} of ${formatNumber(plan.eligible_employees)} eligible`}
                  icon={Users}
                />
                <StatTile
                  label="Average deferral"
                  value={formatPercent(plan.average_deferral_rate, { decimals: 1 })}
                  hint={`Roth adoption ${formatPercent(metrics.roth_adoption, { decimals: 0 })}`}
                  icon={PiggyBank}
                />
                <StatTile
                  label="Average balance"
                  value={formatCurrency(metrics.average_balance, { compact: true })}
                  hint={`Median ${formatCurrency(metrics.median_balance, { compact: true })}`}
                />
                <StatTile
                  label="Plan health"
                  value={formatPercent(health.score, { decimals: 0 })}
                  hint={titleCase(health.grade)}
                  tone={GRADE_TONE[health.grade] ?? "primary"}
                  icon={Building2}
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
                <Card>
                  <CardHeader
                    title="Plan health"
                    description="A weighted score across participation, deferrals, balances, beneficiary coverage and plan design."
                    action={<Badge tone={GRADE_TONE[health.grade] ?? "primary"}>{titleCase(health.grade)}</Badge>}
                  />
                  <CardBody className="space-y-4">
                    <div>
                      <div className="flex items-baseline justify-between">
                        <span className="text-2xl font-semibold tabular text-ink">{formatPercent(health.score, { decimals: 0 })}</span>
                        <span className="text-xs text-ink-muted">Composite score</span>
                      </div>
                      <Progress
                        value={health.score}
                        tone={health.score >= 0.8 ? "positive" : health.score >= 0.65 ? "primary" : "warning"}
                        className="mt-2.5"
                      />
                    </div>

                    <ul className="space-y-2.5">
                      {Object.entries(health.components).map(([key, component]) => (
                        <li key={key}>
                          <div className="flex items-baseline justify-between text-xs">
                            <span className="text-ink-muted">
                              {titleCase(key)}
                              <span className="ml-1.5 text-ink-subtle">({formatPercent(component.weight, { decimals: 0 })} weight)</span>
                            </span>
                            <span className="tabular font-medium text-ink">
                              {component.value < 1 && component.value > 0
                                ? formatPercent(component.value, { decimals: 1 })
                                : formatNumber(component.value)}
                            </span>
                          </div>
                          <Progress
                            value={component.score}
                            tone={component.score >= 0.8 ? "positive" : component.score >= 0.5 ? "primary" : "warning"}
                            className="mt-1"
                          />
                        </li>
                      ))}
                    </ul>

                    <CalcDisclosure calculation={dashboard.health} />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="Plan design" description="Features that drive participation and savings rates." />
                  <CardBody>
                    <KeyValue
                      columns={1}
                      items={[
                        { label: "Employer match", value: plan.employer_match_formula },
                        { label: "Vesting schedule", value: plan.vesting_schedule },
                        {
                          label: "Auto-enrolment",
                          value: plan.auto_enrollment ? `Yes, at ${formatPercent(plan.auto_enrollment_rate, { decimals: 0 })}` : "No",
                        },
                        {
                          label: "Auto-escalation",
                          value: plan.auto_escalation ? `Yes, capped at ${formatPercent(plan.auto_escalation_cap, { decimals: 0 })}` : "No",
                        },
                        { label: "Loans permitted", value: plan.loans_allowed ? "Yes" : "No" },
                        { label: "Hardship withdrawals", value: plan.hardship_allowed ? "Yes" : "No" },
                        { label: "Auto-enrolled participants", value: formatNumber(metrics.auto_enrolled) },
                        { label: "Beneficiary coverage", value: formatPercent(metrics.beneficiary_coverage, { decimals: 0 }) },
                      ]}
                    />
                  </CardBody>
                </Card>
              </div>

              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader title="Deferral rates" description="How much participants are saving." />
                  <CardBody>
                    <CategoryBars data={dashboard.deferral_distribution.map((row) => ({ label: row.bucket, value: row.count }))} seriesLabel="Participants" />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="Vesting" description="Employer contribution vesting across the population." />
                  <CardBody>
                    <CategoryBars data={dashboard.vesting_distribution.map((row) => ({ label: row.bucket, value: row.count }))} seriesLabel="Participants" />
                  </CardBody>
                </Card>
              </div>

              <Section title="Plan activity">
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <StatTile
                    label="Employee contributions"
                    value={formatCurrency(metrics.employee_contributions_ytd, { compact: true })}
                    hint="Year to date"
                  />
                  <StatTile
                    label="Employer contributions"
                    value={formatCurrency(metrics.employer_contributions_ytd, { compact: true })}
                    hint="Match and profit sharing"
                  />
                  <StatTile
                    label="Loans outstanding"
                    value={formatNumber(metrics.loans_outstanding)}
                    hint={`${formatCurrency(metrics.loan_balance, { compact: true })} balance · ${metrics.hardship_count} hardship`}
                  />
                  <StatTile
                    label="Engagement"
                    value={formatPercent(metrics.average_engagement, { decimals: 0 })}
                    hint={`${metrics.hce_count} highly compensated · ${metrics.fully_vested} fully vested`}
                  />
                </div>
              </Section>

              <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
                <QuickLink href="/institutional/participants" label="Participants" description="Balances, deferrals and vesting" />
                <QuickLink href="/institutional/investments" label="Investments" description="IPS screening and fiduciary evidence" />
                <QuickLink href="/institutional/fees" label="Plan costs" description="Fee benchmarking and vendor scorecards" />
                <QuickLink
                  href="/institutional/compliance"
                  label="Compliance"
                  description={
                    dashboard.compliance_summary.next_deadline
                      ? `Next deadline ${formatDate(dashboard.compliance_summary.next_deadline)}`
                      : "Testing and filings"
                  }
                />
              </div>
            </>
          );
        }}
      </DataState>
    </div>
  );
}

function QuickLink({ href, label, description }: { href: string; label: string; description: string }) {
  return (
    <Link href={href}>
      <Card className="flex h-full items-center justify-between gap-3 p-4 transition-shadow hover:shadow-raised">
        <span className="min-w-0">
          <span className="block text-sm font-semibold text-ink">{label}</span>
          <span className="mt-0.5 block text-xs text-ink-muted">{description}</span>
        </span>
        <ChevronRight className="size-4 shrink-0 text-ink-subtle" aria-hidden />
      </Card>
    </Link>
  );
}
