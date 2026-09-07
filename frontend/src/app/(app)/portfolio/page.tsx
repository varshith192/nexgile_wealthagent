"use client";

/** Portfolio workspace (§12): allocation, performance, risk, income, drift. */

import { useState } from "react";
import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { formatCurrency, formatPercent, titleCase } from "@/lib/format";
import type { Calculation, PerformancePayload } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, SegmentedControl, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { AllocationDonut, DivergingBars, IndexedComparison } from "@/components/charts";
import { CalcDisclosure, Delta, FreshnessBar } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

const PERIODS = ["1D", "1W", "1M", "3M", "YTD", "1Y", "3Y", "5Y"];

type PortfolioPayload = {
  household_id: string;
  as_of: string;
  valuation: Calculation<{
    market_value: number;
    cost_basis: number;
    unrealized_gain: number;
    unrealized_gain_percent: number;
    day_change: number;
    day_change_percent: number;
    cash: number;
  }>;
  allocation: Calculation<{ total: number; rows: { key: string; label: string; market_value: number; weight: number }[] }>;
  sector_allocation: Calculation<{ total: number; rows: { key: string; label: string; market_value: number; weight: number }[] }>;
  geography_allocation: Calculation<{ total: number; rows: { key: string; label: string; market_value: number; weight: number }[] }>;
  drift: Calculation<{
    rows: { asset_class: string; label: string; current_weight: number; target_weight: number; drift: number; tolerance_band: number; breached: boolean; dollar_drift: number }[];
    max_drift: number;
    breach_count: number;
  }>;
  concentration: Calculation<{
    rows: { symbol: string; name: string; is_single_name: boolean; market_value: number; weight: number; exceeds_threshold: boolean }[];
    top_single_name: { symbol: string; weight: number } | null;
    single_name_weight: number;
    top_five_weight: number;
    hhi: number;
    flagged: { symbol: string; weight: number }[];
  }>;
  risk: Calculation<{ beta: number; volatility: number; equity_exposure: number; cash_exposure: number }>;
  income: Calculation<{
    annual_income: number;
    monthly_income: number;
    portfolio_yield: number;
    municipal_income: number;
    taxable_income: number;
    rows: { symbol: string; name: string; market_value: number; yield: number; annual_income: number; is_municipal: boolean }[];
  }>;
  performance: PerformancePayload;
  targets: { asset_class: string; asset_class_label: string; target_weight: number; tolerance_band: number }[];
  data_freshness: Record<string, "fresh" | "delayed" | "stale" | "unavailable">;
};

export default function PortfolioPage() {
  const { data, error, loading, refetch } = useApi<PortfolioPayload>("/api/portfolio");
  const [tab, setTab] = useState("allocation");
  const [period, setPeriod] = useState("YTD");

  return (
    <div className="space-y-8">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(portfolio) => {
          const valuation = portfolio.valuation.result;
          const risk = portfolio.risk.result;
          const income = portfolio.income.result;
          const drift = portfolio.drift.result;
          const stats = portfolio.performance.risk_adjusted.result;
          const periodReturn = portfolio.performance.periods[period];

          return (
            <>
              <PageHeader
                title="Portfolio"
                description="Allocation, performance, risk and income for the managed portfolio."
                meta={<FreshnessBar freshness={portfolio.data_freshness} asOf={portfolio.as_of} />}
                actions={
                  <Link href="/holdings">
                    <Button size="sm">
                      View holdings <ChevronRight />
                    </Button>
                  </Link>
                }
              />

              <StatRow columns={4}>
                <StatTile
                  label="Market value"
                  value={formatCurrency(valuation.market_value, { compact: true })}
                  delta={valuation.day_change}
                  deltaPercent={valuation.day_change_percent}
                  hint="Change today"
                  tone="primary"
                />
                <StatTile
                  label="Unrealised gain"
                  value={formatCurrency(valuation.unrealized_gain, { compact: true })}
                  deltaPercent={valuation.unrealized_gain_percent}
                  hint={`Cost basis ${formatCurrency(valuation.cost_basis, { compact: true })}`}
                />
                <StatTile
                  label={`${period} return`}
                  value={formatPercent(periodReturn?.return, { signed: true })}
                  hint={`Benchmark ${formatPercent(periodReturn?.benchmark_return, { signed: true })} · excess ${formatPercent(periodReturn?.excess_return, { signed: true })}`}
                  tone={periodReturn?.excess_return >= 0 ? "positive" : "warning"}
                />
                <StatTile
                  label="Forward income"
                  value={formatCurrency(income.annual_income, { compact: true })}
                  hint={`${formatPercent(income.portfolio_yield, { decimals: 2 })} yield · ${formatCurrency(income.monthly_income)} a month`}
                />
              </StatRow>

              {/* --------------------------------------------- Performance */}
              <Card>
                <CardHeader
                  title="Performance"
                  description={
                    portfolio.performance.benchmark
                      ? `Time-weighted return against ${portfolio.performance.benchmark.name}.`
                      : "Time-weighted return."
                  }
                  action={
                    <SegmentedControl
                      options={PERIODS.map((value) => ({ value, label: value }))}
                      value={period}
                      onChange={setPeriod}
                    />
                  }
                />
                <CardBody className="space-y-6">
                  <IndexedComparison
                    data={portfolio.performance.series}
                    benchmarkName={portfolio.performance.benchmark?.name ?? "Benchmark"}
                    height={280}
                  />

                  <div className="scroll-x rounded-md border border-border">
                    <Table>
                      <THead>
                        <TR>
                          <TH>Period</TH>
                          <TH align="right">Portfolio</TH>
                          <TH align="right">Benchmark</TH>
                          <TH align="right">Excess</TH>
                          <TH align="right">Annualised</TH>
                        </TR>
                      </THead>
                      <tbody>
                        {PERIODS.map((key) => {
                          const row = portfolio.performance.periods[key];
                          if (!row) return null;
                          return (
                            <TR key={key} className={key === period ? "bg-primary-soft/40" : undefined}>
                              <TD className="font-medium">{key}</TD>
                              <TD align="right" numeric>
                                {formatPercent(row.return, { signed: true })}
                              </TD>
                              <TD align="right" numeric className="text-ink-muted">
                                {formatPercent(row.benchmark_return, { signed: true })}
                              </TD>
                              <TD align="right">
                                <Delta percent={row.excess_return} showIcon={false} />
                              </TD>
                              <TD align="right" numeric className="text-ink-muted">
                                {row.annualized_return !== null ? formatPercent(row.annualized_return, { signed: true }) : "—"}
                              </TD>
                            </TR>
                          );
                        })}
                      </tbody>
                    </Table>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    <KeyValue
                      columns={1}
                      items={[
                        { label: "Annualised volatility", value: formatPercent(stats.volatility, { decimals: 1 }) },
                        { label: "Sharpe ratio", value: stats.sharpe_ratio.toFixed(2) },
                      ]}
                    />
                    <KeyValue
                      columns={1}
                      items={[
                        { label: "Maximum drawdown", value: formatPercent(stats.max_drawdown, { decimals: 1 }) },
                        { label: "Tracking error", value: formatPercent(stats.tracking_error, { decimals: 1 }) },
                      ]}
                    />
                    <KeyValue
                      columns={1}
                      items={[
                        { label: "Information ratio", value: stats.information_ratio.toFixed(2) },
                        { label: "Portfolio beta", value: risk.beta.toFixed(2) },
                      ]}
                    />
                  </div>

                  <CalcDisclosure calculation={portfolio.performance.risk_adjusted} label="How these statistics are calculated" />
                </CardBody>
              </Card>

              {/* --------------------------------------------- Allocation */}
              <Card>
                <CardHeader title="Allocation" description="The same portfolio viewed three ways." />
                <div className="px-5">
                  <Tabs
                    value={tab}
                    onChange={setTab}
                    tabs={[
                      { value: "allocation", label: "Asset class" },
                      { value: "sector", label: "Sector" },
                      { value: "geography", label: "Geography" },
                      { value: "drift", label: "Drift vs policy", count: drift.breach_count },
                    ]}
                  />
                </div>
                <CardBody>
                  {tab === "drift" ? (
                    <div className="space-y-5">
                      <DivergingBars
                        data={drift.rows.map((row) => ({ label: row.label, value: row.drift, band: row.tolerance_band }))}
                        height={Math.max(200, drift.rows.length * 34)}
                      />
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Asset class</TH>
                              <TH align="right">Current</TH>
                              <TH align="right">Target</TH>
                              <TH align="right">Drift</TH>
                              <TH align="right">Band</TH>
                              <TH align="right">Dollar gap</TH>
                              <TH align="right">Status</TH>
                            </TR>
                          </THead>
                          <tbody>
                            {drift.rows.map((row) => (
                              <TR key={row.asset_class}>
                                <TD className="font-medium">{row.label}</TD>
                                <TD align="right" numeric>{formatPercent(row.current_weight, { decimals: 1 })}</TD>
                                <TD align="right" numeric className="text-ink-muted">{formatPercent(row.target_weight, { decimals: 1 })}</TD>
                                <TD align="right"><Delta percent={row.drift} showIcon={false} /></TD>
                                <TD align="right" numeric className="text-ink-muted">±{formatPercent(row.tolerance_band, { decimals: 1 })}</TD>
                                <TD align="right" numeric>{formatCurrency(row.dollar_drift, { compact: true, signed: true })}</TD>
                                <TD align="right">
                                  <Badge tone={row.breached ? "warning" : "positive"}>
                                    {row.breached ? "Outside band" : "Within band"}
                                  </Badge>
                                </TD>
                              </TR>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                      <CalcDisclosure calculation={portfolio.drift} />
                    </div>
                  ) : (
                    <div className="space-y-5">
                      <AllocationDonut
                        data={(tab === "allocation"
                          ? portfolio.allocation.result.rows
                          : tab === "sector"
                            ? portfolio.sector_allocation.result.rows
                            : portfolio.geography_allocation.result.rows
                        ).map((row) => ({ label: row.label, value: row.market_value, weight: row.weight }))}
                        height={250}
                        centerLabel="Total"
                        centerValue={formatCurrency(portfolio.allocation.result.total, { compact: true })}
                      />
                      <CalcDisclosure
                        calculation={
                          tab === "allocation"
                            ? portfolio.allocation
                            : tab === "sector"
                              ? portfolio.sector_allocation
                              : portfolio.geography_allocation
                        }
                      />
                    </div>
                  )}
                </CardBody>
              </Card>

              {/* ------------------------------------ Concentration + income */}
              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader
                    title="Concentration"
                    description="Single-name risk measured separately from diversified fund positions."
                  />
                  <CardBody className="space-y-4">
                    <KeyValue
                      items={[
                        { label: "Top five weight", value: formatPercent(portfolio.concentration.result.top_five_weight, { decimals: 1 }) },
                        { label: "Single names total", value: formatPercent(portfolio.concentration.result.single_name_weight, { decimals: 1 }) },
                        { label: "Concentration index (HHI)", value: portfolio.concentration.result.hhi.toFixed(3) },
                        {
                          label: "Largest single name",
                          value: portfolio.concentration.result.top_single_name
                            ? `${portfolio.concentration.result.top_single_name.symbol} · ${formatPercent(portfolio.concentration.result.top_single_name.weight, { decimals: 1 })}`
                            : "None",
                        },
                      ]}
                    />
                    <div className="scroll-x rounded-md border border-border">
                      <Table>
                        <THead>
                          <TR>
                            <TH>Position</TH>
                            <TH align="right">Value</TH>
                            <TH align="right">Weight</TH>
                          </TR>
                        </THead>
                        <tbody>
                          {portfolio.concentration.result.rows.slice(0, 8).map((row) => (
                            <TR key={row.symbol}>
                              <TD>
                                <span className="flex items-center gap-2">
                                  <span className="font-medium">{row.symbol}</span>
                                  {row.is_single_name ? <Badge tone="outline" size="sm">Single name</Badge> : null}
                                  {row.exceeds_threshold ? <Badge tone="warning" size="sm">Above policy</Badge> : null}
                                </span>
                                <span className="mt-0.5 block truncate text-xs text-ink-muted">{row.name}</span>
                              </TD>
                              <TD align="right" numeric>{formatCurrency(row.market_value, { compact: true })}</TD>
                              <TD align="right" numeric className="font-medium">{formatPercent(row.weight, { decimals: 1 })}</TD>
                            </TR>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                    <CalcDisclosure calculation={portfolio.concentration} />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader
                    title="Income"
                    description="Forward twelve-month income from stated distribution yields."
                  />
                  <CardBody className="space-y-4">
                    <KeyValue
                      items={[
                        { label: "Annual income", value: formatCurrency(income.annual_income) },
                        { label: "Monthly average", value: formatCurrency(income.monthly_income) },
                        { label: "Taxable income", value: formatCurrency(income.taxable_income) },
                        { label: "Municipal income", value: formatCurrency(income.municipal_income) },
                      ]}
                    />
                    <div className="scroll-x rounded-md border border-border">
                      <Table>
                        <THead>
                          <TR>
                            <TH>Holding</TH>
                            <TH align="right">Yield</TH>
                            <TH align="right">Annual income</TH>
                          </TR>
                        </THead>
                        <tbody>
                          {income.rows.slice(0, 8).map((row) => (
                            <TR key={`${row.symbol}-${row.annual_income}`}>
                              <TD>
                                <span className="flex items-center gap-2 font-medium">
                                  {row.symbol}
                                  {row.is_municipal ? <Badge tone="positive" size="sm">Tax exempt</Badge> : null}
                                </span>
                                <span className="mt-0.5 block truncate text-xs text-ink-muted">{row.name}</span>
                              </TD>
                              <TD align="right" numeric>{formatPercent(row.yield, { decimals: 2 })}</TD>
                              <TD align="right" numeric className="font-medium">{formatCurrency(row.annual_income)}</TD>
                            </TR>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                    <CalcDisclosure calculation={portfolio.income} />
                  </CardBody>
                </Card>
              </div>

              <Section title="Policy targets" description="The strategic allocation this portfolio is managed against.">
                <Card>
                  <Table>
                    <THead>
                      <TR>
                        <TH>Asset class</TH>
                        <TH align="right">Target</TH>
                        <TH align="right">Tolerance band</TH>
                        <TH align="right">Current</TH>
                      </TR>
                    </THead>
                    <tbody>
                      {portfolio.targets.map((target) => {
                        const current = portfolio.allocation.result.rows.find((row) => row.key === target.asset_class);
                        return (
                          <TR key={target.asset_class}>
                            <TD className="font-medium">{target.asset_class_label ?? titleCase(target.asset_class)}</TD>
                            <TD align="right" numeric>{formatPercent(target.target_weight, { decimals: 1 })}</TD>
                            <TD align="right" numeric className="text-ink-muted">±{formatPercent(target.tolerance_band, { decimals: 1 })}</TD>
                            <TD align="right" numeric className="font-medium">
                              {current ? formatPercent(current.weight, { decimals: 1 }) : "—"}
                            </TD>
                          </TR>
                        );
                      })}
                    </tbody>
                  </Table>
                </Card>
              </Section>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
