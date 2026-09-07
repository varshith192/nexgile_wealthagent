"use client";

/** Advisor portfolio tools (§22): risk, liquidity, correlation, frontier, stress, ESG. */

import { useState } from "react";

import { formatCurrency, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Card, CardBody, CardHeader, Select, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { CategoryBars, FrontierChart } from "@/components/charts";
import { CalcDisclosure } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

type AdvisorPortfolio = {
  household_id: string;
  analytics: {
    as_of: string;
    correlation: Calculation<{
      matrix: Record<string, Record<string, number>>;
      capital_market_assumptions: Record<string, { expected_return: number; volatility: number }>;
    }>;
    efficient_frontier: Calculation<{
      frontier: { label: string; equity_weight: number; expected_return: number; volatility: number; sharpe: number }[];
      current: { label: string; expected_return: number; volatility: number; sharpe: number };
    }>;
    stress_tests: Calculation<{
      scenarios: { key: string; label: string; portfolio_impact_percent: number; portfolio_impact_amount: number; resulting_value: number }[];
      worst_case: { label: string; portfolio_impact_percent: number; portfolio_impact_amount: number } | null;
    }>;
    liquidity: Calculation<{
      buckets: { bucket: string; market_value: number; weight: number }[];
      liquid_value: number;
      liquid_percent: number;
      illiquid_percent: number;
    }>;
    esg: Calculation<{
      portfolio_score: number;
      coverage: number;
      unscored_value: number;
      below_screen: { symbol: string; name: string; esg_score: number; market_value: number }[];
      below_screen_value: number;
    }>;
    risk: Calculation<{ beta: number; volatility: number; equity_exposure: number; cash_exposure: number }>;
    strategic_targets: { asset_class: string; asset_class_label: string; target_weight: number; tolerance_band: number }[];
    tactical_targets: { asset_class: string; asset_class_label: string; target_weight: number }[];
  };
  allocation: Calculation<{ total: number; rows: { key: string; label: string; market_value: number; weight: number }[] }>;
  valuation: Calculation<{ market_value: number }>;
};

const BUCKET_LABELS: Record<string, string> = {
  immediate: "Immediate",
  under_1_week: "Under 1 week",
  under_1_month: "Under 1 month",
  over_1_month: "Over 1 month",
};

export default function AdvisorPortfolioPage() {
  const { data: clients } = useApi<{ clients: { household_id: string; name: string }[] }>("/api/advisor/clients");
  const [householdId, setHouseholdId] = useState("");
  const path = householdId ? `/api/advisor/portfolio?household_id=${householdId}` : "/api/advisor/portfolio";
  const { data, error, loading, refetch } = useApi<AdvisorPortfolio>(path, [householdId]);
  const [tab, setTab] = useState("risk");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Portfolio tools"
        description="Risk, liquidity, correlation, the efficient frontier, stress tests and ESG screening — all from transparent, disclosed assumptions."
        actions={
          <Select
            value={householdId}
            onChange={(event) => setHouseholdId(event.target.value)}
            className="h-9 w-60 text-xs"
            aria-label="Choose a household"
          >
            <option value="">Default household</option>
            {clients?.clients.map((client) => (
              <option key={client.household_id} value={client.household_id}>
                {client.name}
              </option>
            ))}
          </Select>
        }
      />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(payload) => {
          const analytics = payload.analytics;
          const risk = analytics.risk.result;
          const liquidity = analytics.liquidity.result;
          const esg = analytics.esg.result;
          const stress = analytics.stress_tests.result;

          return (
            <>
              <StatRow columns={4}>
                <StatTile label="Portfolio beta" value={risk.beta.toFixed(2)} tone="primary" />
                <StatTile label="Estimated volatility" value={formatPercent(risk.volatility, { decimals: 1 })} />
                <StatTile
                  label="Liquid within a week"
                  value={formatPercent(liquidity.liquid_percent, { decimals: 1 })}
                  hint={formatCurrency(liquidity.liquid_value, { compact: true })}
                />
                <StatTile
                  label="Worst stress scenario"
                  value={stress.worst_case ? formatPercent(stress.worst_case.portfolio_impact_percent, { decimals: 1 }) : "—"}
                  hint={stress.worst_case?.label}
                  tone="warning"
                />
              </StatRow>

              <Card>
                <div className="px-5 pt-4">
                  <Tabs
                    value={tab}
                    onChange={setTab}
                    tabs={[
                      { value: "risk", label: "Risk" },
                      { value: "frontier", label: "Efficient frontier" },
                      { value: "stress", label: "Stress tests", count: stress.scenarios.length },
                      { value: "liquidity", label: "Liquidity" },
                      { value: "correlation", label: "Correlation" },
                      { value: "esg", label: "ESG", count: esg.below_screen.length },
                      { value: "targets", label: "Allocation policy" },
                    ]}
                  />
                </div>

                <CardBody className="space-y-5">
                  {tab === "risk" ? (
                    <>
                      <KeyValue
                        columns={2}
                        items={[
                          { label: "Portfolio beta", value: risk.beta.toFixed(3) },
                          { label: "Weighted volatility", value: formatPercent(risk.volatility, { decimals: 2 }) },
                          { label: "Equity exposure", value: formatPercent(risk.equity_exposure, { decimals: 1 }) },
                          { label: "Cash exposure", value: formatPercent(risk.cash_exposure, { decimals: 1 }) },
                        ]}
                      />
                      <CalcDisclosure calculation={analytics.risk} />
                    </>
                  ) : null}

                  {tab === "frontier" ? (
                    <>
                      <FrontierChart
                        frontier={analytics.efficient_frontier.result.frontier}
                        current={analytics.efficient_frontier.result.current}
                        height={300}
                      />
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Mix</TH>
                              <TH align="right">Expected return</TH>
                              <TH align="right">Volatility</TH>
                              <TH align="right">Sharpe</TH>
                            </TR>
                          </THead>
                          <tbody>
                            {analytics.efficient_frontier.result.frontier.map((point) => (
                              <TR key={point.label}>
                                <TD className="font-medium">{point.label}</TD>
                                <TD align="right" numeric>{formatPercent(point.expected_return, { decimals: 2 })}</TD>
                                <TD align="right" numeric>{formatPercent(point.volatility, { decimals: 2 })}</TD>
                                <TD align="right" numeric>{point.sharpe.toFixed(2)}</TD>
                              </TR>
                            ))}
                            <TR className="bg-primary-soft/40">
                              <TD className="font-semibold">Current portfolio</TD>
                              <TD align="right" numeric className="font-semibold">
                                {formatPercent(analytics.efficient_frontier.result.current.expected_return, { decimals: 2 })}
                              </TD>
                              <TD align="right" numeric className="font-semibold">
                                {formatPercent(analytics.efficient_frontier.result.current.volatility, { decimals: 2 })}
                              </TD>
                              <TD align="right" numeric className="font-semibold">
                                {analytics.efficient_frontier.result.current.sharpe.toFixed(2)}
                              </TD>
                            </TR>
                          </tbody>
                        </Table>
                      </div>
                      <CalcDisclosure calculation={analytics.efficient_frontier} />
                    </>
                  ) : null}

                  {tab === "stress" ? (
                    <>
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Scenario</TH>
                              <TH align="right">Portfolio impact</TH>
                              <TH align="right">Dollar impact</TH>
                              <TH align="right">Resulting value</TH>
                            </TR>
                          </THead>
                          <tbody>
                            {stress.scenarios.map((scenario) => (
                              <TR key={scenario.key}>
                                <TD className="font-medium">{scenario.label}</TD>
                                <TD align="right" numeric className="font-medium text-negative">
                                  {formatPercent(scenario.portfolio_impact_percent, { decimals: 1 })}
                                </TD>
                                <TD align="right" numeric className="text-negative">
                                  {formatCurrency(scenario.portfolio_impact_amount, { compact: true })}
                                </TD>
                                <TD align="right" numeric>{formatCurrency(scenario.resulting_value, { compact: true })}</TD>
                              </TR>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                      <CalcDisclosure calculation={analytics.stress_tests} />
                    </>
                  ) : null}

                  {tab === "liquidity" ? (
                    <>
                      <CategoryBars
                        data={liquidity.buckets.map((bucket) => ({
                          label: BUCKET_LABELS[bucket.bucket] ?? titleCase(bucket.bucket),
                          value: bucket.market_value,
                        }))}
                        seriesLabel="Market value"
                        formatValue={(value) => formatCurrency(value, { compact: true })}
                        height={230}
                      />
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Availability</TH>
                              <TH align="right">Market value</TH>
                              <TH align="right">Weight</TH>
                            </TR>
                          </THead>
                          <tbody>
                            {liquidity.buckets.map((bucket) => (
                              <TR key={bucket.bucket}>
                                <TD className="font-medium">{BUCKET_LABELS[bucket.bucket] ?? titleCase(bucket.bucket)}</TD>
                                <TD align="right" numeric>{formatCurrency(bucket.market_value, { compact: true })}</TD>
                                <TD align="right" numeric>{formatPercent(bucket.weight, { decimals: 1 })}</TD>
                              </TR>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                      <CalcDisclosure calculation={analytics.liquidity} />
                    </>
                  ) : null}

                  {tab === "correlation" ? (
                    <>
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Asset class</TH>
                              {Object.keys(analytics.correlation.result.matrix).map((key) => (
                                <TH key={key} align="right">
                                  {titleCase(key).split(" ").map((word) => word[0]).join("")}
                                </TH>
                              ))}
                            </TR>
                          </THead>
                          <tbody>
                            {Object.entries(analytics.correlation.result.matrix).map(([rowKey, row]) => (
                              <TR key={rowKey}>
                                <TD className="whitespace-nowrap font-medium">{titleCase(rowKey)}</TD>
                                {Object.entries(row).map(([columnKey, value]) => (
                                  <TD
                                    key={columnKey}
                                    align="right"
                                    numeric
                                    className={cn(
                                      value >= 0.7 && rowKey !== columnKey && "font-semibold text-warning",
                                      rowKey === columnKey && "text-ink-subtle",
                                    )}
                                  >
                                    {value.toFixed(2)}
                                  </TD>
                                ))}
                              </TR>
                            ))}
                          </tbody>
                        </Table>
                      </div>

                      <div>
                        <p className="section-label">Capital market assumptions</p>
                        <div className="mt-2.5 scroll-x rounded-md border border-border">
                          <Table>
                            <THead>
                              <TR>
                                <TH>Asset class</TH>
                                <TH align="right">Expected return</TH>
                                <TH align="right">Volatility</TH>
                              </TR>
                            </THead>
                            <tbody>
                              {Object.entries(analytics.correlation.result.capital_market_assumptions).map(([key, value]) => (
                                <TR key={key}>
                                  <TD className="font-medium">{titleCase(key)}</TD>
                                  <TD align="right" numeric>{formatPercent(value.expected_return, { decimals: 2 })}</TD>
                                  <TD align="right" numeric>{formatPercent(value.volatility, { decimals: 2 })}</TD>
                                </TR>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      </div>

                      <CalcDisclosure calculation={analytics.correlation} />
                    </>
                  ) : null}

                  {tab === "esg" ? (
                    <>
                      <KeyValue
                        columns={3}
                        items={[
                          { label: "Portfolio ESG score", value: esg.portfolio_score.toFixed(1) },
                          { label: "Coverage", value: formatPercent(esg.coverage, { decimals: 1 }) },
                          { label: "Unscored value", value: formatCurrency(esg.unscored_value, { compact: true }) },
                        ]}
                      />
                      {esg.below_screen.length === 0 ? (
                        <p className="text-sm text-ink-muted">Every scored holding clears the screen.</p>
                      ) : (
                        <div className="scroll-x rounded-md border border-border">
                          <Table>
                            <THead>
                              <TR>
                                <TH>Holding</TH>
                                <TH align="right">ESG score</TH>
                                <TH align="right">Market value</TH>
                              </TR>
                            </THead>
                            <tbody>
                              {esg.below_screen.map((row) => (
                                <TR key={row.symbol}>
                                  <TD>
                                    <span className="font-medium">{row.symbol}</span>
                                    <span className="mt-0.5 block max-w-[16rem] truncate text-xs text-ink-muted">{row.name}</span>
                                  </TD>
                                  <TD align="right" numeric className="font-medium text-warning">{row.esg_score.toFixed(0)}</TD>
                                  <TD align="right" numeric>{formatCurrency(row.market_value, { compact: true })}</TD>
                                </TR>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      )}
                      <CalcDisclosure calculation={analytics.esg} />
                    </>
                  ) : null}

                  {tab === "targets" ? (
                    <div className="scroll-x rounded-md border border-border">
                      <Table>
                        <THead>
                          <TR>
                            <TH>Asset class</TH>
                            <TH align="right">Strategic target</TH>
                            <TH align="right">Tactical target</TH>
                            <TH align="right">Tolerance band</TH>
                            <TH align="right">Current</TH>
                          </TR>
                        </THead>
                        <tbody>
                          {analytics.strategic_targets.map((target) => {
                            const tactical = analytics.tactical_targets.find((row) => row.asset_class === target.asset_class);
                            const current = payload.allocation.result.rows.find((row) => row.key === target.asset_class);
                            return (
                              <TR key={target.asset_class}>
                                <TD className="font-medium">{target.asset_class_label}</TD>
                                <TD align="right" numeric>{formatPercent(target.target_weight, { decimals: 1 })}</TD>
                                <TD align="right" numeric className="text-ink-muted">
                                  {tactical ? formatPercent(tactical.target_weight, { decimals: 1 }) : "—"}
                                </TD>
                                <TD align="right" numeric className="text-ink-muted">
                                  ±{formatPercent(target.tolerance_band, { decimals: 1 })}
                                </TD>
                                <TD align="right" numeric className="font-medium">
                                  {current ? formatPercent(current.weight, { decimals: 1 }) : "—"}
                                </TD>
                              </TR>
                            );
                          })}
                        </tbody>
                      </Table>
                    </div>
                  ) : null}
                </CardBody>
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
