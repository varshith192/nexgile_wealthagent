"use client";

/** Tax Center (§15). Nothing here trades; opportunities route through approval. */

import { useState } from "react";
import { CalendarClock, Receipt, ShieldAlert, TrendingDown, TrendingUp } from "lucide-react";

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
  unrealized_gain: number;
  harvestable_gain?: number;
  holding_period: string;
  acquired_on: string;
  applicable_rate: number;
  estimated_tax_benefit: number;
  rationale: string;
  replacement_symbol?: string | null;
};

type TaxPayload = {
  tax_year: number;
  financial_year: string;
  as_of: string;
  rates: { marginal: number; long_term_capital_gains: number; regime: string };
  realized_gains: Calculation<{
    equity_stcg: number; equity_ltcg: number; other_stcg: number; other_ltcg: number;
    total_stcg: number; total_ltcg: number; net_gain: number; transaction_count: number;
  }>;
  tax_estimate: Calculation<{
    exemption_used: number; exemption_remaining: number;
    base_tax: number; surcharge: number; cess: number; total_tax: number;
    effective_rate: number; loss_carry_forward: number; net_gain: number;
  }>;
  harvest: Calculation<{
    loss_opportunities: HarvestRow[];
    gain_opportunities: HarvestRow[];
    opportunity_count: number;
    total_harvestable_loss: number;
    total_harvestable_gain: number;
    total_estimated_benefit: number;
    loss_benefit: number;
    gain_benefit: number;
    exemption_remaining_after: number;
  }>;
  asset_location: Calculation<{
    by_tax_treatment: Record<string, number>;
    misplaced: { symbol: string; name: string; asset_class: string; current_location: string; preferred_location: string; market_value: number; estimated_annual_drag: number }[];
    total_estimated_drag: number;
  }>;
  capital_gains_budget: Calculation<{ budget: number; used: number; remaining: number; utilisation: number; over_budget: boolean }>;
  tax_free_income: number;
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
  nps_annuitization: {
    required_amount: number;
    purchased_amount: number;
    remaining: number;
    is_required: boolean;
    status: string;
    accounts: { id: string; corpus_at_exit: number; required_annuity_amount: number; annuity_purchased_amount: number; exit_deadline: string; status: string; annuity_provider: string | null }[];
  };
  regime_comparison: Calculation<{
    old_regime_tax: number;
    new_regime_tax: number;
    recommended_regime: string;
    annual_saving: number;
    old_effective_rate: number;
    new_effective_rate: number;
    deduction_breakeven: number | null;
  }> | null;
  advance_tax: Calculation<{
    is_liable: boolean;
    instalments: { label: string; due_date: string; cumulative_percent: number; cumulative_due: number; instalment: number; is_past: boolean }[];
    cumulative_due_to_date: number;
    tax_paid: number;
    shortfall: number;
    on_schedule: boolean;
  }>;
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
    financial_year: string;
    regime: string;
    estimated_income_tax: number;
    estimated_capital_gains_tax: number;
    estimated_total_tax: number;
    effective_rate: number;
    assumptions: string[];
    limitations: string[];
  };
};

type ChapterViaPayload = Calculation<{
  sections: { section: string; label: string; limit: number; invested: number; claimed: number; headroom: number; fully_used: boolean }[];
  total_deductions: number;
  total_headroom: number;
  sections_fully_used: number;
}>;

export default function TaxPage() {
  const { data, error, loading, refetch } = useApi<TaxPayload>("/api/tax");
  const chapterVia = useApi<ChapterViaPayload>("/api/tax/chapter-via");
  const [tab, setTab] = useState("harvesting");

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(tax) => {
          const realized = tax.realized_gains.result;
          const estimate = tax.tax_estimate.result;
          const harvest = tax.harvest.result;
          const budget = tax.capital_gains_budget.result;
          const nps = tax.nps_annuitization;

          return (
            <>
              <PageHeader
                title="Tax Center"
                description="Realised gains, harvesting candidates and year-end estimates. Every figure is a planning estimate, not a computation of your income tax return."
                meta={
                  <>
                    <Badge tone="outline">FY {tax.financial_year}</Badge>
                    <Badge tone="outline">{titleCase(tax.rates.regime)} regime</Badge>
                    <Badge tone="outline">Marginal {formatPercent(tax.rates.marginal, { decimals: 0 })}</Badge>
                    <Badge tone="outline">LTCG {formatPercent(tax.rates.long_term_capital_gains, { decimals: 1 })}</Badge>
                    <span className="text-xs text-ink-muted">As of {formatDate(tax.as_of)}</span>
                  </>
                }
              />

              <StatRow columns={4}>
                <StatTile
                  label="Net realised gain"
                  value={formatCurrency(realized.net_gain, { compact: true })}
                  hint={`${formatCurrency(realized.total_stcg, { compact: true })} short · ${formatCurrency(realized.total_ltcg, { compact: true })} long`}
                  icon={Receipt}
                />
                <StatTile
                  label="Estimated capital gains tax"
                  value={formatCurrency(estimate.total_tax, { compact: true })}
                  hint={`${formatCurrency(estimate.exemption_remaining, { compact: true })} of the 112A exemption unused`}
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

              {/* --------------------------------------- NPS annuitization */}
              {nps.is_required && nps.remaining > 0 ? (
                <Card className="border-negative/25 bg-negative-soft/40">
                  <CardBody className="flex flex-wrap items-center gap-4 py-4">
                    <ShieldAlert className="size-5 shrink-0 text-negative" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-ink">NPS annuitization not yet purchased</p>
                      <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                        {formatCurrency(nps.remaining)} of {formatCurrency(nps.required_amount)} required annuity
                        purchase is outstanding. PFRDA exit regulations require at least 40% of the Tier I corpus to
                        buy an annuity at exit.
                      </p>
                      <Progress
                        value={nps.purchased_amount / Math.max(nps.required_amount, 1)}
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
                      { value: "regime", label: "Old vs new regime" },
                      { value: "chapter_via", label: "Chapter VI-A" },
                      { value: "charitable", label: "Charitable" },
                      { value: "projection", label: "Projection" },
                    ]}
                  />
                </div>

                <CardBody className="space-y-5">
                  {tab === "harvesting" ? (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-ink">Loss and gain harvesting candidates</p>
                          <p className="mt-0.5 text-xs text-ink-muted">
                            India has no wash-sale rule: a loss can be booked and repurchased immediately, and a
                            long-term equity gain can be booked inside the unused section 112A exemption to reset the
                            cost base at no tax cost.
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="section-label">Total estimated benefit</p>
                          <p className="text-lg font-semibold tabular text-ink">
                            {formatCurrency(harvest.total_estimated_benefit, { compact: true })}
                          </p>
                        </div>
                      </div>

                      <div>
                        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                          <TrendingDown className="size-3.5" aria-hidden /> Loss harvest candidates
                        </p>
                        {harvest.loss_opportunities.length === 0 ? (
                          <EmptyState title="No loss candidates" description="No open lot currently holds a loss above the review threshold." />
                        ) : (
                          <HarvestTable rows={harvest.loss_opportunities} negative />
                        )}
                      </div>

                      <div>
                        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                          <TrendingUp className="size-3.5" aria-hidden /> Gain harvest candidates (section 112A exemption)
                        </p>
                        {harvest.gain_opportunities.length === 0 ? (
                          <EmptyState title="No gain candidates" description="No long-term equity lot qualifies, or the exemption is already used." />
                        ) : (
                          <HarvestTable rows={harvest.gain_opportunities} negative={false} />
                        )}
                      </div>

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
                                    <TD><Badge tone="positive" size="sm">{row.preferred_location}</Badge></TD>
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

                  {tab === "regime" ? (
                    tax.regime_comparison ? (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <p className="text-sm text-ink-muted">
                            Every taxpayer chooses the old or the new regime afresh each financial year. The new
                            regime is the default.
                          </p>
                          <Badge tone="positive">
                            {titleCase(tax.regime_comparison.result.recommended_regime)} regime recommended
                          </Badge>
                        </div>
                        <KeyValue
                          columns={2}
                          items={[
                            { label: "Old regime tax", value: formatCurrency(tax.regime_comparison.result.old_regime_tax) },
                            { label: "New regime tax", value: formatCurrency(tax.regime_comparison.result.new_regime_tax) },
                            { label: "Annual saving", value: formatCurrency(tax.regime_comparison.result.annual_saving) },
                            { label: "Old effective rate", value: formatPercent(tax.regime_comparison.result.old_effective_rate, { decimals: 1 }) },
                            { label: "New effective rate", value: formatPercent(tax.regime_comparison.result.new_effective_rate, { decimals: 1 }) },
                            {
                              label: "Deductions needed for the old regime to win",
                              value: tax.regime_comparison.result.deduction_breakeven != null
                                ? formatCurrency(tax.regime_comparison.result.deduction_breakeven, { compact: true })
                                : "Not achievable",
                            },
                          ]}
                        />
                        <CalcDisclosure calculation={tax.regime_comparison} />
                      </>
                    ) : (
                      <EmptyState title="No income on file" description="Add annual income to compare the two regimes." />
                    )
                  ) : null}

                  {tab === "chapter_via" ? (
                    <DataState loading={chapterVia.loading} error={chapterVia.error} data={chapterVia.data}>
                      {(via) => (
                        <>
                          <KeyValue
                            columns={3}
                            items={[
                              { label: "Total deductions", value: formatCurrency(via.result.total_deductions) },
                              { label: "Headroom remaining", value: formatCurrency(via.result.total_headroom) },
                              { label: "Sections fully used", value: `${via.result.sections_fully_used} of ${via.result.sections.length}` },
                            ]}
                          />
                          <div className="scroll-x rounded-md border border-border">
                            <Table>
                              <THead>
                                <TR>
                                  <TH>Section</TH>
                                  <TH align="right">Limit</TH>
                                  <TH align="right">Invested</TH>
                                  <TH align="right">Claimed</TH>
                                  <TH align="right">Headroom</TH>
                                </TR>
                              </THead>
                              <tbody>
                                {via.result.sections.map((row) => (
                                  <TR key={row.section}>
                                    <TD>
                                      <span className="font-medium">{row.section}</span>
                                      <span className="mt-0.5 block text-xs text-ink-muted">{row.label}</span>
                                    </TD>
                                    <TD align="right" numeric>{formatCurrency(row.limit, { compact: true })}</TD>
                                    <TD align="right" numeric>{formatCurrency(row.invested, { compact: true })}</TD>
                                    <TD align="right" numeric className="font-medium">{formatCurrency(row.claimed, { compact: true })}</TD>
                                    <TD align="right" numeric className={cn(row.fully_used ? "text-ink-subtle" : "text-positive")}>
                                      {row.fully_used ? "Fully used" : formatCurrency(row.headroom, { compact: true })}
                                    </TD>
                                  </TR>
                                ))}
                              </tbody>
                            </Table>
                          </div>
                          <CalcDisclosure calculation={via} />
                        </>
                      )}
                    </DataState>
                  ) : null}

                  {tab === "charitable" ? (
                    tax.charitable_securities.length === 0 ? (
                      <EmptyState title="No long-term appreciated positions" description="Gifting appreciated shares requires a position held more than a year with a meaningful gain." />
                    ) : (
                      <>
                        <p className="text-sm text-ink-muted">
                          Gifting these long-term appreciated positions to a registered charity avoids the capital
                          gain entirely while the household can claim relief under section 80G.
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
                          { label: "Estimated income tax", value: formatCurrency(tax.projection.estimated_income_tax, { compact: true }) },
                          { label: "Estimated capital gains tax", value: formatCurrency(tax.projection.estimated_capital_gains_tax, { compact: true }) },
                          { label: "Estimated total", value: formatCurrency(tax.projection.estimated_total_tax, { compact: true }) },
                          { label: "Effective rate", value: formatPercent(tax.projection.effective_rate, { decimals: 1 }) },
                          { label: "Regime", value: titleCase(tax.projection.regime) },
                          { label: "Tax-free income", value: formatCurrency(tax.tax_free_income) },
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

              {/* --------------------------------- Advance tax + NPS annuitization */}
              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader
                    title="Advance tax schedule"
                    description="Section 208 instalments: 15%, 45%, 75% and 100% of the estimated annual liability."
                  />
                  <CardBody className="space-y-4">
                    <KeyValue
                      columns={2}
                      items={[
                        { label: "Liable to pay", value: tax.advance_tax.result.is_liable ? "Yes" : "No" },
                        { label: "Due to date", value: formatCurrency(tax.advance_tax.result.cumulative_due_to_date) },
                        { label: "Paid", value: formatCurrency(tax.advance_tax.result.tax_paid) },
                        { label: "Shortfall", value: formatCurrency(tax.advance_tax.result.shortfall) },
                      ]}
                    />
                    <ul className="divide-y divide-border rounded-md border border-border">
                      {tax.advance_tax.result.instalments.map((row) => (
                        <li key={row.label} className="flex items-center justify-between gap-3 px-3.5 py-2.5">
                          <div>
                            <p className="text-sm font-medium text-ink">{row.label}</p>
                            <p className="text-2xs text-ink-subtle">{formatDate(row.due_date)} · {formatPercent(row.cumulative_percent, { decimals: 0 })} cumulative</p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-medium tabular text-ink">{formatCurrency(row.cumulative_due, { compact: true })}</p>
                            <Badge tone={row.is_past ? "neutral" : "outline"} size="sm">{row.is_past ? "Past" : "Upcoming"}</Badge>
                          </div>
                        </li>
                      ))}
                    </ul>
                    <CalcDisclosure calculation={tax.advance_tax} />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="NPS annuitization" description="At least 40% of the Tier I corpus must buy an annuity at exit." />
                  {!nps.is_required ? (
                    <EmptyState title="Not yet applicable" description="No member in this household is within five years of NPS exit." />
                  ) : (
                    <CardBody className="space-y-4">
                      <KeyValue
                        items={[
                          { label: "Required this year", value: formatCurrency(nps.required_amount) },
                          { label: "Purchased to date", value: formatCurrency(nps.purchased_amount) },
                          { label: "Remaining", value: formatCurrency(nps.remaining) },
                        ]}
                      />
                      <Progress
                        value={nps.purchased_amount / Math.max(nps.required_amount, 1)}
                        tone={nps.remaining > 0 ? "warning" : "positive"}
                        showTrackLabel
                      />
                      {nps.accounts.length > 0 ? (
                        <div className="scroll-x rounded-md border border-border">
                          <Table>
                            <THead>
                              <TR>
                                <TH>Corpus at exit</TH>
                                <TH align="right">Required</TH>
                                <TH align="right">Purchased</TH>
                                <TH>Exit deadline</TH>
                              </TR>
                            </THead>
                            <tbody>
                              {nps.accounts.map((row) => (
                                <TR key={row.id}>
                                  <TD numeric>{formatCurrency(row.corpus_at_exit, { compact: true })}</TD>
                                  <TD align="right" numeric className="font-medium">{formatCurrency(row.required_annuity_amount)}</TD>
                                  <TD align="right" numeric>{formatCurrency(row.annuity_purchased_amount)}</TD>
                                  <TD className="text-xs">{formatDate(row.exit_deadline, "long")}</TD>
                                </TR>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      ) : null}
                    </CardBody>
                  )}
                </Card>
              </div>

              <Section title="Realised gains" description={`Settled sales recorded in FY ${tax.financial_year}.`}>
                <Card>
                  <CardBody className="space-y-4">
                    <KeyValue
                      columns={3}
                      items={[
                        { label: "Short-term gain", value: formatCurrency(realized.total_stcg) },
                        { label: "Long-term gain", value: formatCurrency(realized.total_ltcg) },
                        { label: "Net gain", value: formatCurrency(realized.net_gain) },
                        { label: "Capital gains tax estimate", value: formatCurrency(estimate.total_tax) },
                        { label: "Surcharge + cess", value: formatCurrency(estimate.surcharge + estimate.cess) },
                        {
                          label: "Loss carried forward",
                          value: formatCurrency(estimate.loss_carry_forward),
                          hint: "Usable for eight assessment years if the return is filed on time.",
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

function HarvestTable({ rows, negative }: { rows: HarvestRow[]; negative: boolean }) {
  return (
    <div className="scroll-x rounded-md border border-border">
      <Table>
        <THead>
          <TR>
            <TH>Security</TH>
            <TH>Account</TH>
            <TH align="right">Quantity</TH>
            <TH align="right">Cost basis</TH>
            <TH align="right">Market value</TH>
            <TH align="right">{negative ? "Unrealised loss" : "Unrealised gain"}</TH>
            <TH>Period</TH>
            <TH align="right">Est. benefit</TH>
            <TH>Replacement</TH>
          </TR>
        </THead>
        <tbody>
          {rows.map((row) => (
            <TR key={row.lot_id}>
              <TD>
                <span className="font-medium">{row.symbol}</span>
                <span className="mt-0.5 block max-w-[14rem] truncate text-xs text-ink-muted">{row.name}</span>
                <span className="mt-0.5 block text-2xs text-ink-subtle">Acquired {formatDate(row.acquired_on)}</span>
              </TD>
              <TD className="text-xs text-ink-muted">{row.account_name}</TD>
              <TD align="right" numeric>{formatNumber(row.quantity, 2)}</TD>
              <TD align="right" numeric>{formatCurrency(row.cost_basis)}</TD>
              <TD align="right" numeric>{formatCurrency(row.market_value)}</TD>
              <TD align="right" numeric className={cn("font-medium", negative ? "text-negative" : "text-positive")}>
                {formatCurrency(negative ? row.unrealized_gain : row.harvestable_gain ?? row.unrealized_gain)}
              </TD>
              <TD>
                <Badge tone={row.holding_period === "long_term" ? "positive" : "neutral"} size="sm">
                  {row.holding_period === "long_term" ? "Long" : "Short"}
                </Badge>
              </TD>
              <TD align="right" numeric className="font-medium text-positive">
                {formatCurrency(row.estimated_tax_benefit)}
              </TD>
              <TD className="text-xs">{row.replacement_symbol ?? "—"}</TD>
            </TR>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
