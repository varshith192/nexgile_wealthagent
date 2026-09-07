"use client";

/** Participant portal overview (§33). */

import Link from "next/link";
import { ChevronRight, GraduationCap, PiggyBank, Scale, ShieldCheck, Target, TriangleAlert } from "lucide-react";

import { formatCurrency, formatDate, formatPercent, titleCase } from "@/lib/format";
import type { ParticipantPortal } from "@/lib/participant";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, Progress } from "@/components/ui";
import { StackedBars } from "@/components/charts";
import { CalcDisclosure, ProjectionNotice, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

const STATUS_TONE: Record<string, "positive" | "warning" | "negative" | "primary"> = {
  on_track: "positive",
  monitor: "primary",
  at_risk: "warning",
};

export default function ParticipantPage() {
  const { data, error, loading, refetch } = useApi<ParticipantPortal>("/api/participant");

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(portal) => {
          const participant = portal.participant;
          const readiness = portal.readiness.projection.result;
          const capacity = portal.contributions.capacity.result;
          const vesting = portal.vesting.result;

          return (
            <>
              <PageHeader
                title={`Welcome, ${participant.full_name.split(" ")[0]}`}
                description={`${portal.plan.name} · ${portal.plan.sponsor}`}
                meta={
                  <>
                    <Badge tone="outline">{portal.plan.plan_type.toUpperCase()}</Badge>
                    <Badge tone="outline">Age {participant.age}</Badge>
                    <Badge tone="outline">{participant.years_of_service.toFixed(1)} years of service</Badge>
                    <span className="text-xs text-ink-muted">As of {formatDate(portal.as_of)}</span>
                  </>
                }
                actions={
                  <Link href="/participant/retirement">
                    <Button variant="primary" size="sm">
                      <Target />
                      Check my readiness
                    </Button>
                  </Link>
                }
              />

              {!participant.has_beneficiary ? (
                <Card className="border-warning/25 bg-warning-soft/40">
                  <CardBody className="flex flex-wrap items-center gap-3 py-4">
                    <TriangleAlert className="size-4 shrink-0 text-warning" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-ink">You have not named a beneficiary</p>
                      <p className="mt-0.5 text-xs text-ink-muted">
                        Your beneficiary designation overrides your will for this account. Without one, the balance
                        goes through probate.
                      </p>
                    </div>
                    <Link href="/participant/beneficiaries">
                      <Button size="sm">Add a beneficiary</Button>
                    </Link>
                  </CardBody>
                </Card>
              ) : null}

              <StatRow columns={4}>
                <StatTile
                  label="Account balance"
                  value={formatCurrency(participant.account_balance, { compact: true })}
                  hint={`${formatCurrency(participant.vested_balance, { compact: true })} vested`}
                  icon={PiggyBank}
                  tone="primary"
                />
                <StatTile
                  label="Your contribution rate"
                  value={formatPercent(participant.deferral_rate + participant.roth_deferral_rate, { decimals: 1 })}
                  hint={
                    participant.roth_deferral_rate > 0
                      ? `incl. ${formatPercent(participant.roth_deferral_rate, { decimals: 1 })} Roth`
                      : "Pre-tax only"
                  }
                  href="/participant/contributions"
                />
                <StatTile
                  label="Vested"
                  value={formatPercent(vesting.vested_percentage, { decimals: 0 })}
                  hint={vesting.fully_vested ? "Fully vested" : `${vesting.schedule} schedule`}
                  tone={vesting.fully_vested ? "positive" : "warning"}
                  icon={Scale}
                />
                <StatTile
                  label="Retirement readiness"
                  value={formatPercent(readiness.replacement_ratio, { decimals: 0 })}
                  hint={`Income replacement · ${titleCase(readiness.status)}`}
                  tone={STATUS_TONE[readiness.status] ?? "primary"}
                  icon={Target}
                  href="/participant/retirement"
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
                <Card>
                  <CardHeader
                    title="Contribution history"
                    description="Your contributions and what your employer added, by quarter."
                    action={
                      <Link href="/participant/contributions">
                        <Button variant="ghost" size="sm">
                          Detail <ChevronRight />
                        </Button>
                      </Link>
                    }
                  />
                  <CardBody>
                    <StackedBars
                      data={portal.contributions.history.slice(-8).map((row) => ({
                        label: formatDate(row.period_end, "short"),
                        "Pre-tax": row.employee_pretax,
                        Roth: row.employee_roth,
                        "Catch-up": row.employee_catchup,
                        "Employer match": row.employer_match,
                        "Profit sharing": row.employer_profit_sharing,
                      }))}
                      keys={[
                        { key: "Pre-tax", label: "Pre-tax" },
                        { key: "Roth", label: "Roth" },
                        { key: "Catch-up", label: "Catch-up" },
                        { key: "Employer match", label: "Employer match" },
                        { key: "Profit sharing", label: "Profit sharing" },
                      ]}
                      height={240}
                    />
                    <div className="mt-5 border-t border-border pt-4">
                      <KeyValue
                        columns={3}
                        items={[
                          { label: "Your contributions this year", value: formatCurrency(portal.contributions.ytd_employee) },
                          { label: "Employer contributions", value: formatCurrency(portal.contributions.ytd_employer) },
                          { label: "Remaining room", value: formatCurrency(capacity.remaining_capacity) },
                        ]}
                      />
                    </div>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="Contribution room" description="How much you can still contribute this year." />
                  <CardBody className="space-y-4">
                    <div>
                      <div className="flex items-baseline justify-between text-sm">
                        <span className="text-ink-muted">Used</span>
                        <span className="tabular font-medium text-ink">
                          {formatCurrency(capacity.ytd_deferral)} of {formatCurrency(capacity.annual_limit)}
                        </span>
                      </div>
                      <Progress
                        value={capacity.ytd_deferral / capacity.annual_limit}
                        tone={capacity.on_pace_to_max ? "positive" : "primary"}
                        className="mt-2"
                        showTrackLabel
                      />
                    </div>

                    <KeyValue
                      columns={1}
                      items={[
                        { label: "Annual limit", value: formatCurrency(capacity.annual_limit) },
                        {
                          label: "Catch-up eligible",
                          value: capacity.catchup_eligible ? `Yes · ${formatCurrency(capacity.catchup_amount)}` : "Not yet (age 50)",
                        },
                        { label: "Projected for the year", value: formatCurrency(capacity.projected_deferral) },
                        { label: "Rate needed to max out", value: formatPercent(capacity.required_rate_to_max, { decimals: 1 }) },
                      ]}
                    />

                    {!capacity.on_pace_to_max ? (
                      <p className="rounded-md bg-primary-soft px-3 py-2.5 text-xs leading-relaxed text-primary">
                        Raising your rate to {formatPercent(capacity.required_rate_to_max, { decimals: 1 })} would use
                        the full annual limit. Employer match is only earned on what you contribute.
                      </p>
                    ) : null}

                    <CalcDisclosure calculation={portal.contributions.capacity} />
                  </CardBody>
                </Card>
              </div>

              <Section title="Your plan">
                <div className="grid gap-6 lg:grid-cols-3">
                  <Card>
                    <CardHeader title="Plan features" />
                    <CardBody>
                      <KeyValue
                        columns={1}
                        items={[
                          { label: "Employer match", value: portal.plan.employer_match_formula },
                          { label: "Vesting", value: portal.plan.vesting_schedule },
                          { label: "Auto-enrolment", value: portal.plan.auto_enrollment ? "Yes" : "No" },
                          { label: "Auto-escalation", value: portal.plan.auto_escalation ? "Yes" : "No" },
                          { label: "Loans permitted", value: portal.plan.loans_allowed ? "Yes" : "No" },
                          { label: "Recordkeeper", value: portal.plan.recordkeeper },
                        ]}
                      />
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader title="Balance breakdown" />
                    <CardBody>
                      <KeyValue
                        columns={1}
                        items={[
                          { label: "Total balance", value: formatCurrency(participant.account_balance) },
                          { label: "Roth balance", value: formatCurrency(participant.roth_balance) },
                          { label: "Employer balance", value: formatCurrency(participant.employer_balance) },
                          { label: "Vested balance", value: formatCurrency(participant.vested_balance) },
                          { label: "Years of service", value: `${participant.years_of_service.toFixed(1)} years` },
                          { label: "Target retirement age", value: String(participant.retirement_age) },
                        ]}
                      />
                      <CalcDisclosure calculation={portal.vesting} className="mt-4" label="How vesting is calculated" />
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader
                      title="Learning"
                      description={`${formatPercent(portal.education.completion_rate, { decimals: 0 })} complete`}
                      action={
                        <Link href="/participant/education">
                          <Button variant="ghost" size="sm">
                            <GraduationCap />
                          </Button>
                        </Link>
                      }
                    />
                    <CardBody className="space-y-3">
                      {portal.education.paths.map((path) => (
                        <div key={path.learning_path}>
                          <div className="flex items-baseline justify-between text-xs">
                            <span className="text-ink-muted">{path.learning_path}</span>
                            <span className="tabular text-ink">
                              {path.completed}/{path.total}
                            </span>
                          </div>
                          <Progress value={path.progress} tone={path.progress >= 1 ? "positive" : "primary"} className="mt-1" />
                        </div>
                      ))}
                    </CardBody>
                  </Card>
                </div>
              </Section>

              <Card>
                <CardHeader
                  title="Retirement outlook"
                  description="What your current plan projects, and what it assumes."
                  action={
                    <Link href="/participant/retirement">
                      <Button variant="ghost" size="sm">
                        Run scenarios <ChevronRight />
                      </Button>
                    </Link>
                  }
                />
                <CardBody className="space-y-4">
                  <KeyValue
                    columns={3}
                    items={[
                      { label: "Projected balance at retirement", value: formatCurrency(readiness.projected_balance, { compact: true }) },
                      { label: "Projected annual income", value: formatCurrency(readiness.total_projected_income, { compact: true }) },
                      { label: "Target income", value: formatCurrency(readiness.target_income, { compact: true }) },
                      {
                        label: readiness.income_gap >= 0 ? "Projected surplus" : "Projected gap",
                        value: formatCurrency(Math.abs(readiness.income_gap), { compact: true }),
                      },
                      { label: "Income replacement", value: formatPercent(readiness.replacement_ratio, { decimals: 0 }) },
                      { label: "Years to retirement", value: String(readiness.years_to_retirement) },
                    ]}
                  />
                  <ProjectionNotice />
                  <CalcDisclosure calculation={portal.readiness.projection} />
                </CardBody>
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
