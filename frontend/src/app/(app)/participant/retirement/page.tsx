"use client";

/**
 * Retirement readiness (§34).
 *
 * Change an input, re-run the projection. Inputs, assumptions and limitations
 * are all on screen — a projection you cannot interrogate is not much use.
 */

import { useState } from "react";
import { Play, RotateCcw, Target } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatPercent, titleCase } from "@/lib/format";
import type { Readiness } from "@/lib/participant";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Field, Input, TD, TH, THead, TR, Table } from "@/components/ui";
import { CategoryBars, PercentileBand } from "@/components/charts";
import { CalcDisclosure, ProjectionNotice } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

const STATUS_TONE: Record<string, "positive" | "warning" | "negative" | "primary"> = {
  on_track: "positive",
  monitor: "primary",
  at_risk: "warning",
};

export default function RetirementReadinessPage() {
  const { data, error, loading, refetch } = useApi<Readiness>("/api/participant/readiness");
  const [custom, setCustom] = useState<Readiness | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});

  const active = custom ?? data;

  const { run: recalculate, pending } = useMutation(async () => {
    const body: Record<string, number> = {};
    for (const [key, value] of Object.entries(form)) {
      if (value !== "" && !Number.isNaN(Number(value))) body[key] = Number(value);
    }
    const result = await api.post<Readiness>("/api/participant/readiness", body);
    setCustom(result);
    return result;
  });

  const reset = () => {
    setCustom(null);
    setForm({});
    refetch();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Retirement readiness"
        description="Where your current plan lands, and what changes when you adjust the inputs."
        actions={
          custom ? (
            <Button size="sm" onClick={reset}>
              <RotateCcw />
              Reset to my plan
            </Button>
          ) : undefined
        }
      />

      <DataState loading={loading} error={error} data={active} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(readiness) => {
          const projection = readiness.projection.result;
          const monteCarlo = readiness.monte_carlo.result;
          const inputs = readiness.inputs;

          return (
            <>
              {custom ? (
                <div className="rounded-md border border-primary/25 bg-primary-soft/40 px-4 py-3 text-sm text-ink">
                  Showing a what-if projection with your adjusted inputs. Nothing has been saved to your plan.
                </div>
              ) : null}

              <StatRow columns={4}>
                <StatTile
                  label="Projected balance"
                  value={formatCurrency(projection.projected_balance, { compact: true })}
                  hint={`At age ${inputs.retirement_age}`}
                  tone="primary"
                  icon={Target}
                />
                <StatTile
                  label="Projected annual income"
                  value={formatCurrency(projection.total_projected_income, { compact: true })}
                  hint={`Against a ${formatCurrency(projection.target_income, { compact: true })} target`}
                />
                <StatTile
                  label="Income replacement"
                  value={formatPercent(projection.replacement_ratio, { decimals: 0 })}
                  hint={titleCase(projection.status)}
                  tone={STATUS_TONE[projection.status] ?? "primary"}
                />
                <StatTile
                  label={projection.income_gap >= 0 ? "Projected surplus" : "Projected gap"}
                  value={formatCurrency(Math.abs(projection.income_gap), { compact: true })}
                  hint={
                    projection.additional_annual_contribution > 0
                      ? `${formatCurrency(projection.additional_annual_contribution)} more a year closes it`
                      : "On plan"
                  }
                  tone={projection.income_gap >= 0 ? "positive" : "warning"}
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1fr_1.5fr]">
                <Card>
                  <CardHeader title="Adjust the inputs" description="Change anything and re-run. Your saved plan is untouched." />
                  <CardBody className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Current age">
                        <Input
                          type="number"
                          min={18}
                          max={100}
                          placeholder={String(inputs.current_age)}
                          value={form.current_age ?? ""}
                          onChange={(event) => setForm({ ...form, current_age: event.target.value })}
                        />
                      </Field>
                      <Field label="Retirement age">
                        <Input
                          type="number"
                          min={40}
                          max={100}
                          placeholder={String(inputs.retirement_age)}
                          value={form.retirement_age ?? ""}
                          onChange={(event) => setForm({ ...form, retirement_age: event.target.value })}
                        />
                      </Field>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Current savings">
                        <Input
                          type="number"
                          min={0}
                          step={1000}
                          placeholder={String(Math.round(inputs.current_savings))}
                          value={form.current_savings ?? ""}
                          onChange={(event) => setForm({ ...form, current_savings: event.target.value })}
                        />
                      </Field>
                      <Field label="Annual income">
                        <Input
                          type="number"
                          min={0}
                          step={1000}
                          placeholder={String(Math.round(inputs.annual_income))}
                          value={form.annual_income ?? ""}
                          onChange={(event) => setForm({ ...form, annual_income: event.target.value })}
                        />
                      </Field>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Contribution rate" hint="0.10 means 10% of pay">
                        <Input
                          type="number"
                          min={0}
                          max={1}
                          step={0.01}
                          placeholder={inputs.deferral_rate.toFixed(2)}
                          value={form.deferral_rate ?? ""}
                          onChange={(event) => setForm({ ...form, deferral_rate: event.target.value })}
                        />
                      </Field>
                      <Field label="Expected return" hint="0.065 means 6.5% a year">
                        <Input
                          type="number"
                          min={-0.2}
                          max={0.3}
                          step={0.005}
                          placeholder={inputs.expected_return.toFixed(3)}
                          value={form.expected_return ?? ""}
                          onChange={(event) => setForm({ ...form, expected_return: event.target.value })}
                        />
                      </Field>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Social Security (annual)">
                        <Input
                          type="number"
                          min={0}
                          step={1000}
                          placeholder="estimated"
                          value={form.social_security_annual ?? ""}
                          onChange={(event) => setForm({ ...form, social_security_annual: event.target.value })}
                        />
                      </Field>
                      <Field label="Healthcare cost (annual)">
                        <Input
                          type="number"
                          min={0}
                          step={500}
                          placeholder="12000"
                          value={form.healthcare_annual ?? ""}
                          onChange={(event) => setForm({ ...form, healthcare_annual: event.target.value })}
                        />
                      </Field>
                    </div>

                    <Button variant="primary" className="w-full" loading={pending} onClick={() => recalculate()}>
                      <Play />
                      Recalculate
                    </Button>

                    {inputs.employer_match_formula ? (
                      <p className="text-xs leading-relaxed text-ink-muted">
                        Employer match: {inputs.employer_match_formula}. The projection includes the match you earn at
                        the contribution rate above.
                      </p>
                    ) : null}
                  </CardBody>
                </Card>

                <div className="space-y-6">
                  <Card>
                    <CardHeader
                      title="Range of outcomes"
                      description={`${monteCarlo.trials.toLocaleString()} simulated paths. Success means ${monteCarlo.success_basis}.`}
                      action={
                        <Badge tone={monteCarlo.success_rate >= 0.7 ? "positive" : monteCarlo.success_rate >= 0.4 ? "warning" : "negative"}>
                          {formatPercent(monteCarlo.success_rate, { decimals: 0 })} success
                        </Badge>
                      }
                    />
                    <CardBody className="space-y-4">
                      <PercentileBand
                        data={[
                          { label: "Today", p10: inputs.current_savings, p50: inputs.current_savings, p90: inputs.current_savings },
                          {
                            label: `Age ${inputs.retirement_age}`,
                            p10: monteCarlo.percentiles.p10,
                            p50: monteCarlo.percentiles.p50,
                            p90: monteCarlo.percentiles.p90,
                          },
                        ]}
                        height={220}
                      />
                      <KeyValue
                        columns={3}
                        items={[
                          { label: "10th percentile", value: formatCurrency(monteCarlo.percentiles.p10, { compact: true }) },
                          { label: "Median", value: formatCurrency(monteCarlo.percentiles.p50, { compact: true }) },
                          { label: "90th percentile", value: formatCurrency(monteCarlo.percentiles.p90, { compact: true }) },
                          {
                            label: "Balance needed",
                            value: monteCarlo.success_threshold ? formatCurrency(monteCarlo.success_threshold, { compact: true }) : "—",
                          },
                          { label: "Paths reaching it", value: `${monteCarlo.successful_trials} of ${monteCarlo.trials}` },
                          { label: "Deterministic projection", value: formatCurrency(monteCarlo.deterministic_projection, { compact: true }) },
                        ]}
                      />
                      <CalcDisclosure calculation={readiness.monte_carlo} label="How the simulation works" />
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader title="What changes the outcome" description="The same projection with one input moved." />
                    <CardBody className="space-y-5">
                      <CategoryBars
                        data={readiness.scenarios.map((scenario) => ({ label: scenario.label, value: scenario.projected_balance }))}
                        seriesLabel="Projected balance"
                        formatValue={(value) => formatCurrency(value, { compact: true })}
                        height={220}
                      />
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Scenario</TH>
                              <TH align="right">Balance</TH>
                              <TH align="right">Income</TH>
                              <TH align="right">Replacement</TH>
                              <TH align="right">Gap</TH>
                              <TH align="right">Status</TH>
                            </TR>
                          </THead>
                          <tbody>
                            {readiness.scenarios.map((scenario) => (
                              <TR key={scenario.label} className={scenario.is_baseline ? "bg-surface-muted/60" : undefined}>
                                <TD>
                                  <span className="flex items-center gap-2 font-medium">
                                    {scenario.label}
                                    {scenario.is_baseline ? <Badge tone="outline" size="sm">Base</Badge> : null}
                                  </span>
                                </TD>
                                <TD align="right" numeric>{formatCurrency(scenario.projected_balance, { compact: true })}</TD>
                                <TD align="right" numeric>{formatCurrency(scenario.total_projected_income, { compact: true })}</TD>
                                <TD align="right" numeric>{formatPercent(scenario.replacement_ratio, { decimals: 0 })}</TD>
                                <TD
                                  align="right"
                                  numeric
                                  className={cn(scenario.income_gap >= 0 ? "text-positive" : "text-negative")}
                                >
                                  {formatCurrency(scenario.income_gap, { compact: true, signed: true })}
                                </TD>
                                <TD align="right">
                                  <Badge tone={STATUS_TONE[scenario.status] ?? "neutral"}>{titleCase(scenario.status)}</Badge>
                                </TD>
                              </TR>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                    </CardBody>
                  </Card>
                </div>
              </div>

              <Card>
                <CardHeader title="Projection detail" description="Every component of the income estimate." />
                <CardBody className="space-y-4">
                  <KeyValue
                    columns={3}
                    items={[
                      { label: "Portfolio income", value: formatCurrency(projection.portfolio_income, { compact: true }) },
                      { label: "Social Security", value: formatCurrency(projection.social_security_income, { compact: true }) },
                      { label: "Other income", value: formatCurrency(projection.other_income, { compact: true }) },
                      { label: "Healthcare costs", value: formatCurrency(projection.healthcare_costs, { compact: true }) },
                      { label: "Balance required", value: formatCurrency(projection.required_balance, { compact: true }) },
                      { label: "Balance gap", value: formatCurrency(projection.balance_gap, { compact: true }) },
                      { label: "Years to retirement", value: String(projection.years_to_retirement) },
                      { label: "Years in retirement", value: String(projection.years_in_retirement) },
                      { label: "Readiness score", value: formatPercent(projection.readiness_score, { decimals: 0 }) },
                    ]}
                  />
                  <ProjectionNotice />
                  <CalcDisclosure calculation={readiness.projection} />
                </CardBody>
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
