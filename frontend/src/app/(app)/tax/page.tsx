"use client";

/** Tax Center (§15). Nothing here trades; opportunities route through approval. */

import { useState } from "react";
import { AlertTriangle, CalendarClock, Receipt, ShieldAlert, TrendingDown } from "lucide-react";

import { formatCurrency, formatDate, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Card, CardBody, CardHeader, Progress, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { CalcDisclosure, SeverityBadge, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type HarvestRow = {
  lot_id: string;
  symbol: string;
  name: string;
  account_name: string;
  quantity: number;
  cost_basis: number;
  market_value: number;
  unrealized_loss: number;
  holding_period: string;
  acquired_on: string;
  applicable_rate: number;
  estimated_tax_benefit: number;
  wash_sale_risk: string;
  replacement_symbol: string | null;
};

type TaxPayload = {
  tax_year: number;
  as_of: string;
  rates: { marginal: number; long_term_capital_gains: number; state: number };
  realized_gains: Calculation<{ short_term_gain: number; long_term_gain: number; net_gain: number; transaction_count: number }>;
  tax_estimate: Calculation<{
    federal_tax: number;
    state_tax: number;
    total_tax: number;
    effective_rate: number;
    ordinary_income_offset: number;
    loss_carryforward: number;
  }>;
  harvest: Calculation<{
    opportunities: HarvestRow[];
    opportunity_count: number;
    total_harvestable_loss: number;
    total_estimated_benefit: number;
  }>;
  asset_location: Calculation<{
    by_tax_treatment: Record<string, number>;
    misplaced: { symbol: string; name: string; asset_class: string; current_location: string; preferred_location: string; market_value: number; estimated_annual_drag: number }[];
    total_estimated_drag: number;
  }>;
  capital_gains_budget: Calculation<{ budget: number; used: number; remaining: number; utilisation: number; over_budget: boolean }>;
  municipal_income: number;
  opportunities: {
    id: string;
    opportunity_type: string;
    title: string;
    description: string;
    estimated_benefit: number;
    severity: string;
    status: string;
    deadline: string | null;
    assumptions: string[];
  }[];
  rmd: {
    required_amount: number;
    distributed_amount: number;
    remaining: number;
    deadline: string;
    is_required: boolean;
    status: string;
    accounts: { id: string; required_amount: number; distributed_amount: number; life_expectancy_factor: number; prior_year_end_balance: number; status: string }[];
    calculation: Calculation<Record<string, unknown>> | null;
  };
  roth_conversion: Calculation<{
    tax_due_now: number;
    projected_balance_at_retirement: number;
    tax_if_not_converted: number;
    after_tax_value_roth: number;
    after_tax_value_traditional: number;
    net_benefit: number;
    favourable: boolean;
  }>;
  wash_sale_windows: {
    id: string;
    account_name: string;
    symbol: string;
    security_name: string;
    window_start: string;
    window_end: string;
    reason: string;
    is_active: boolean;
    days_remaining: number;
  }[];
  charitable_securities: {
    holding_id: string;
    symbol: string;
    name: string;
    account_name: string;
    market_value: number;
    cost_basis: number;
    unrealized_gain: number;
    capital_gains_tax_avoided: number;
  }[];
  projection: {
    tax_year: number;
    estimated_ordinary_income_tax: number;
    estimated_state_tax: number;
    estimated_capital_gains_tax: number;
    estimated_total_tax: number;
    effective_rate: number;
    assumptions: string[];
    limitations: string[];
  };
};

export default function TaxPage() {
  const { data, error, loading, refetch } = useApi<TaxPayload>("/api/tax");
  const [tab, setTab] = useState("harvesting");

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(tax) => {
          const realized = tax.realized_gains.result;
          const estimate = tax.tax_estimate.result;
          const harvest = tax.harvest.result;
          const budget = tax.capital_gains_budget.result;

          return (
            <>
              <PageHeader
                title="Tax Center"
                description="Realised gains, harvesting candidates and year-end estimates. Every figure is a planning estimate, not a tax return calculation."
                meta={
                  <>
                    <Badge tone="outline">Tax year {tax.tax_year}</Badge>
                    <Badge tone="outline">Marginal {formatPercent(tax.rates.marginal, { decimals: 0 })}</Badge>
                    <Badge tone="outline">LTCG {formatPercent(tax.rates.long_term_capital_gains, { decimals: 0 })}</Badge>
                    <Badge tone="outline">State {formatPercent(tax.rates.state, { decimals: 2 })}</Badge>
                    <span className="text-xs text-ink-muted">As of {formatDate(tax.as_of)}</span>
                  </>
                }
              />

              <StatRow columns={4}>
                <StatTile
                  label="Net realised gain"
                  value={formatCurrency(realized.net_gain, { compact: true })}
                  hint={`${formatCurrency(realized.short_term_gain, { compact: true })} short · ${formatCurrency(realized.long_term_gain, { compact: true })} long`}
                  icon={Receipt}
                />
                <StatTile
                  label="Estimated tax on gains"
                  value={formatCurrency(estimate.total_tax, { compact: true })}
                  hint={`${formatCurrency(estimate.federal_tax, { compact: true })} federal · ${formatCurrency(estimate.state_tax, { compact: true })} state`}
                />
                <StatTile
                  label="Harvesting opportunity"
                  value={formatCurrency(harvest.total_estimated_benefit, { compact: true })}
                  hint={`${harvest.opportunity_count} candidate${harvest.opportunity_count === 1 ? "" : "s"}`}
                  tone={harvest.opportunity_count ? "primary" : "default"}
                  icon={TrendingDown}
                />
                <StatTile
                  label="Gain budget remaining"
                  value={formatCurrency(budget.remaining, { compact: true })}
                  hint={`${formatPercent(budget.utilisation, { decimals: 0 })} of ${formatCurrency(budget.budget, { compact: true })} used`}
                  tone={budget.over_budget ? "negative" : "default"}
                />
              </StatRow>

              {/* --------------------------------------- RMD + wash sales */}
              {tax.rmd.is_required && tax.rmd.remaining > 0 ? (
                <Card className="border-negative/25 bg-negative-soft/40">
                  <CardBody className="flex flex-wrap items-center gap-4 py-4">
                    <ShieldAlert className="size-5 shrink-0 text-negative" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-ink">Required minimum distribution outstanding</p>
                      <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                        {formatCurrency(tax.rmd.remaining)} of {formatCurrency(tax.rmd.required_amount)} has not yet
                        been distributed. The deadline is {formatDate(tax.rmd.deadline, "long")}. A qualified
                        charitable distribution can satisfy the remainder.
                      </p>
                      <Progress
                        value={tax.rmd.distributed_amount / tax.rmd.required_amount}
                        tone="warning"
                        className="mt-2.5 max-w-md"
                        showTrackLabel
                      />
                    </div>
                  </CardBody>
                </Card>
              ) : null}

              <Card>
                <div className="px-5 pt-4">
                  <Tabs
                    value={tab}
                    onChange={setTab}
                    tabs={[
                      { value: "harvesting", label: "Harvesting", count: harvest.opportunity_count },
                      { value: "opportunities", label: "Opportunities", count: tax.opportunities.length },
                      { value: "location", label: "Asset location", count: tax.asset_location.result.misplaced.length },
                      { value: "roth", label: "Roth conversion" },
                      { value: "charitable", label: "Charitable", count: tax.charitable_securities.length },
                      { value: "projection", label: "Projection" },
                    ]}
                  />
                </div>

                <CardBody className="space-y-5">
                  {tab === "harvesting" ? (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-ink">Tax-loss harvesting candidates</p>
                          <p className="mt-0.5 text-xs text-ink-muted">
                            Open lots holding a loss above the review threshold. Each must clear a wash-sale check
                            and be approved before any action is taken.
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="section-label">Total harvestable loss</p>
                          <p className="text-lg font-semibold tabular text-ink">
                            {formatCurrency(harvest.total_harvestable_loss, { compact: true })}
                          </p>
                        </div>
                      </div>

                      {harvest.opportunities.length === 0 ? (
                        <EmptyState title="No harvesting candidates" description="No open lot currently holds a loss above the threshold." />
                      ) : (
                        <div className="scroll-x rounded-md border border-border">
                          <Table>
                            <THead>
                              <TR>
                                <TH>Security</TH>
                                <TH>Account</TH>
                                <TH align="right">Quantity</TH>
                                <TH align="right">Cost basis</TH>
                                <TH align="right">Market value</TH>
                                <TH align="right">Unrealised loss</TH>
                                <TH>Period</TH>
                                <TH align="right">Est. benefit</TH>
                                <TH>Wash sale</TH>
                                <TH>Replacement</TH>
                              </TR>
                            </THead>
                            <tbody>
                              {harvest.opportunities.map((row) => (
                                <TR key={row.lot_id}>
                                  <TD>
                                    <span className="font-medium">{row.symbol}</span>
                                    <span className="mt-0.5 block max-w-[14rem] truncate text-xs text-ink-muted">{row.name}</span>
                                    <span className="mt-0.5 block text-2xs text-ink-subtle">
                                      Acquired {formatDate(row.acquired_on)}
                                    </span>
                                  </TD>
                                  <TD className="text-xs text-ink-muted">{row.account_name}</TD>
                                  <TD align="right" numeric>{formatNumber(row.quantity, 2)}</TD>
                                  <TD align="right" numeric>{formatCurrency(row.cost_basis)}</TD>
                                  <TD align="right" numeric>{formatCurrency(row.market_value)}</TD>
                                  <TD align="right" numeric className="font-medium text-negative">
                                    {formatCurrency(row.unrealized_loss)}
                                  </TD>
                                  <TD>
                                    <Badge tone={row.holding_period === "long_term" ? "positive" : "neutral"} size="sm">
                                      {row.holding_period === "long_term" ? "Long" : "Short"}
                                    </Badge>
                                  </TD>
                                  <TD align="right" numeric className="font-medium text-positive">
                                    {formatCurrency(row.estimated_tax_benefit)}
                                  </TD>
                                  <TD>
                                    <StatusBadge status={row.wash_sale_risk} />
                                  </TD>
                                  <TD className="text-xs">{row.replacement_symbol ?? "—"}</TD>
                                </TR>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      )}

                      <div className="rounded-md border border-info/25 bg-info-soft px-3.5 py-3">
                        <p className="text-xs font-semibold text-info">Identify → Analyse → Review → Approve → Simulated action</p>
                        <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                          Nexgile never places a trade. Your advisor or tax specialist raises a harvest proposal from
                          the advisor workstation; it is executed in simulation only after approval.
                        </p>
                      </div>

                      <CalcDisclosure calculation={tax.harvest} />
                    </>
                  ) : null}

                  {tab === "opportunities" ? (
                    tax.opportunities.length === 0 ? (
                      <EmptyState title="No open opportunities" />
                    ) : (
                      <ul className="space-y-3">
                        {tax.opportunities.map((opportunity) => (
                          <li key={opportunity.id} className="rounded-lg border border-border p-4">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                  <SeverityBadge severity={opportunity.severity as "low" | "medium" | "high"} />
                                  <Badge tone="outline" size="sm">{titleCase(opportunity.opportunity_type)}</Badge>
                                  <StatusBadge status={opportunity.status} />
                                </div>
                                <p className="mt-2 text-sm font-semibold text-ink">{opportunity.title}</p>
                                <p className="mt-1 text-sm leading-6 text-ink-muted">{opportunity.description}</p>
                                {opportunity.assumptions.length > 0 ? (
                                  <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-ink-subtle">
                                    {opportunity.assumptions.map((assumption) => (
                                      <li key={assumption}>{assumption}</li>
                                    ))}
                                  </ul>
                                ) : null}
                              </div>
                              <div className="shrink-0 text-right">
                                <p className="section-label">Estimated benefit</p>
                                <p className="mt-1 text-lg font-semibold tabular text-positive">
                                  {formatCurrency(opportunity.estimated_benefit, { compact: true })}
                                </p>
                                {opportunity.deadline ? (
                                  <p className="mt-1 flex items-center justify-end gap-1 text-2xs text-ink-subtle">
                                    <CalendarClock className="size-3" aria-hidden />
                                    by {formatDate(opportunity.deadline)}
                                  </p>
                                ) : null}
                              </div>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )
                  ) : null}

                  {tab === "location" ? (
                    <>
                      <KeyValue
                        columns={3}
                        items={Object.entries(tax.asset_location.result.by_tax_treatment).map(([treatment, value]) => ({
                          label: titleCase(treatment),
                          value: formatCurrency(value, { compact: true }),
                        }))}
                      />
                      {tax.asset_location.result.misplaced.length === 0 ? (
                        <EmptyState title="Assets are well located" description="No income-producing asset sits in a taxable account." />
                      ) : (
                        <>
                          <p className="text-sm text-ink-muted">
                            Estimated annual tax drag from asset location:{" "}
                            <span className="font-semibold text-ink">
                              {formatCurrency(tax.asset_location.result.total_estimated_drag)}
                            </span>
                          </p>
                          <div className="scroll-x rounded-md border border-border">
                            <Table>
                              <THead>
                                <TR>
                                  <TH>Holding</TH>
                                  <TH>Asset class</TH>
                                  <TH>Currently in</TH>
                                  <TH>Better in</TH>
                                  <TH align="right">Market value</TH>
                                  <TH align="right">Annual drag</TH>
                                </TR>
                              </THead>
                              <tbody>
                                {tax.asset_location.result.misplaced.map((row) => (
                                  <TR key={row.symbol}>
                                    <TD>
                                      <span className="font-medium">{row.symbol}</span>
                                      <span className="mt-0.5 block max-w-[14rem] truncate text-xs text-ink-muted">{row.name}</span>
                                    </TD>
                                    <TD className="text-xs">{titleCase(row.asset_class)}</TD>
                                    <TD><Badge tone="warning" size="sm">{titleCase(row.current_location)}</Badge></TD>
                                    <TD><Badge tone="positive" size="sm">{titleCase(row.preferred_location)}</Badge></TD>
                                    <TD align="right" numeric>{formatCurrency(row.market_value, { compact: true })}</TD>
                                    <TD align="right" numeric className="font-medium">{formatCurrency(row.estimated_annual_drag)}</TD>
                                  </TR>
                                ))}
                              </tbody>
                            </Table>
                          </div>
                        </>
                      )}
                      <CalcDisclosure calculation={tax.asset_location} />
                    </>
                  ) : null}

                  {tab === "roth" ? (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="text-sm text-ink-muted">
                          Illustrative comparison for a $100,000 conversion, paying the tax from taxable assets.
                        </p>
                        <Badge tone={tax.roth_conversion.result.favourable ? "positive" : "warning"}>
                          {tax.roth_conversion.result.favourable ? "Favourable on these assumptions" : "Not favourable on these assumptions"}
                        </Badge>
                      </div>
                      <KeyValue
                        columns={2}
                        items={[
                          { label: "Tax due on conversion now", value: formatCurrency(tax.roth_conversion.result.tax_due_now) },
                          { label: "Projected balance at retirement", value: formatCurrency(tax.roth_conversion.result.projected_balance_at_retirement, { compact: true }) },
                          { label: "Tax if left pre-tax", value: formatCurrency(tax.roth_conversion.result.tax_if_not_converted, { compact: true }) },
                          { label: "After-tax value — Roth", value: formatCurrency(tax.roth_conversion.result.after_tax_value_roth, { compact: true }) },
                          { label: "After-tax value — Traditional", value: formatCurrency(tax.roth_conversion.result.after_tax_value_traditional, { compact: true }) },
                          { label: "Net benefit", value: formatCurrency(tax.roth_conversion.result.net_benefit, { compact: true, signed: true }) },
                        ]}
                      />
                      <CalcDisclosure calculation={tax.roth_conversion} />
                    </>
                  ) : null}

                  {tab === "charitable" ? (
                    tax.charitable_securities.length === 0 ? (
                      <EmptyState title="No long-term appreciated positions" description="Gifting appreciated shares requires a position held more than a year with a meaningful gain." />
                    ) : (
                      <>
                        <p className="text-sm text-ink-muted">
                          Gifting these long-term appreciated positions avoids the capital gain entirely while
                          preserving the deduction.
                        </p>
                        <div className="scroll-x rounded-md border border-border">
                          <Table>
                            <THead>
                              <TR>
                                <TH>Holding</TH>
                                <TH>Account</TH>
                                <TH align="right">Market value</TH>
                                <TH align="right">Cost basis</TH>
                                <TH align="right">Unrealised gain</TH>
                                <TH align="right">Capital gains tax avoided</TH>
                              </TR>
                            </THead>
                            <tbody>
                              {tax.charitable_securities.map((row) => (
                                <TR key={row.holding_id}>
                                  <TD>
                                    <span className="font-medium">{row.symbol}</span>
                                    <span className="mt-0.5 block max-w-[14rem] truncate text-xs text-ink-muted">{row.name}</span>
                                  </TD>
                                  <TD className="text-xs text-ink-muted">{row.account_name}</TD>
                                  <TD align="right" numeric>{formatCurrency(row.market_value, { compact: true })}</TD>
                                  <TD align="right" numeric className="text-ink-muted">{formatCurrency(row.cost_basis, { compact: true })}</TD>
                                  <TD align="right" numeric className="text-positive">{formatCurrency(row.unrealized_gain, { compact: true })}</TD>
                                  <TD align="right" numeric className="font-medium">{formatCurrency(row.capital_gains_tax_avoided)}</TD>
                                </TR>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      </>
                    )
                  ) : null}

                  {tab === "projection" ? (
                    <>
                      <KeyValue
                        columns={2}
                        items={[
                          { label: "Estimated ordinary income tax", value: formatCurrency(tax.projection.estimated_ordinary_income_tax, { compact: true }) },
                          { label: "Estimated state tax", value: formatCurrency(tax.projection.estimated_state_tax, { compact: true }) },
                          { label: "Estimated capital gains tax", value: formatCurrency(tax.projection.estimated_capital_gains_tax, { compact: true }) },
                          { label: "Estimated total", value: formatCurrency(tax.projection.estimated_total_tax, { compact: true }) },
                          { label: "Effective rate", value: formatPercent(tax.projection.effective_rate, { decimals: 1 }) },
                          { label: "Municipal income (tax exempt)", value: formatCurrency(tax.municipal_income) },
                        ]}
                      />
                      <div>
                        <p className="section-label">Assumptions</p>
                        <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-muted">
                          {tax.projection.assumptions.map((assumption) => (
                            <li key={assumption}>{assumption}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="section-label">Limitations</p>
                        <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-muted">
                          {tax.projection.limitations.map((limitation) => (
                            <li key={limitation}>{limitation}</li>
                          ))}
                        </ul>
                      </div>
                    </>
                  ) : null}
                </CardBody>
              </Card>

              {/* ---------------------------------------- Wash sale + RMD */}
              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader
                    title="Wash-sale monitoring"
                    description="A loss is disallowed if a substantially identical security is bought within 30 days either side of the sale."
                  />
                  {tax.wash_sale_windows.length === 0 ? (
                    <EmptyState title="No active wash-sale windows" description="Nothing currently blocks a loss sale." />
                  ) : (
                    <ul className="divide-y divide-border">
                      {tax.wash_sale_windows.map((window) => (
                        <li key={window.id} className="px-5 py-3.5">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="flex items-center gap-2 text-sm font-medium text-ink">
                                {window.is_active ? <AlertTriangle className="size-3.5 text-warning" aria-hidden /> : null}
                                {window.symbol} · {window.account_name}
                              </p>
                              <p className="mt-0.5 text-xs leading-5 text-ink-muted">{window.reason}</p>
                              <p className="mt-1 text-2xs text-ink-subtle">
                                {formatDate(window.window_start)} – {formatDate(window.window_end)}
                              </p>
                            </div>
                            <Badge tone={window.is_active ? "warning" : "neutral"}>
                              {window.is_active ? `${window.days_remaining}d left` : "Expired"}
                            </Badge>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                <Card>
                  <CardHeader title="Required minimum distributions" description="Calculated from the IRS Uniform Lifetime Table." />
                  {!tax.rmd.is_required ? (
                    <EmptyState title="No distribution required" description="No account owner in this household has reached the required beginning age." />
                  ) : (
                    <CardBody className="space-y-4">
                      <KeyValue
                        items={[
                          { label: "Required this year", value: formatCurrency(tax.rmd.required_amount) },
                          { label: "Distributed to date", value: formatCurrency(tax.rmd.distributed_amount) },
                          { label: "Remaining", value: formatCurrency(tax.rmd.remaining) },
                          { label: "Deadline", value: formatDate(tax.rmd.deadline, "long") },
                        ]}
                      />
                      <Progress
                        value={tax.rmd.distributed_amount / Math.max(tax.rmd.required_amount, 1)}
                        tone={tax.rmd.remaining > 0 ? "warning" : "positive"}
                        showTrackLabel
                      />
                      {tax.rmd.accounts.length > 0 ? (
                        <div className="scroll-x rounded-md border border-border">
                          <Table>
                            <THead>
                              <TR>
                                <TH>Prior year-end balance</TH>
                                <TH align="right">Factor</TH>
                                <TH align="right">Required</TH>
                                <TH align="right">Distributed</TH>
                              </TR>
                            </THead>
                            <tbody>
                              {tax.rmd.accounts.map((row) => (
                                <TR key={row.id}>
                                  <TD numeric>{formatCurrency(row.prior_year_end_balance, { compact: true })}</TD>
                                  <TD align="right" numeric>{row.life_expectancy_factor.toFixed(1)}</TD>
                                  <TD align="right" numeric className="font-medium">{formatCurrency(row.required_amount)}</TD>
                                  <TD align="right" numeric>{formatCurrency(row.distributed_amount)}</TD>
                                </TR>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      ) : null}
                      {tax.rmd.calculation ? <CalcDisclosure calculation={tax.rmd.calculation} /> : null}
                    </CardBody>
                  )}
                </Card>
              </div>

              <Section title="Realised gains" description={`Settled sales recorded in ${tax.tax_year}.`}>
                <Card>
                  <CardBody className="space-y-4">
                    <KeyValue
                      columns={3}
                      items={[
                        { label: "Short-term gain", value: formatCurrency(realized.short_term_gain) },
                        { label: "Long-term gain", value: formatCurrency(realized.long_term_gain) },
                        { label: "Net gain", value: formatCurrency(realized.net_gain) },
                        { label: "Federal tax estimate", value: formatCurrency(estimate.federal_tax) },
                        { label: "State tax estimate", value: formatCurrency(estimate.state_tax) },
                        {
                          label: "Loss carryforward",
                          value: formatCurrency(estimate.loss_carryforward),
                          hint: estimate.ordinary_income_offset ? `${formatCurrency(estimate.ordinary_income_offset)} offsets ordinary income` : undefined,
                        },
                      ]}
                    />
                    <CalcDisclosure calculation={tax.tax_estimate} label="How the tax estimate is calculated" />
                  </CardBody>
                </Card>
              </Section>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
