"use client";

/** Client dashboard (§10). */

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  ChevronRight,
  Layers,
  Scale,
  Sparkles,
  Target,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { formatCurrency, formatDate, formatDateTime, formatPercent } from "@/lib/format";
import type { DashboardPayload } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, Progress, SegmentedControl } from "@/components/ui";
import { AllocationDonut, IndexedComparison, TrendArea } from "@/components/charts";
import {
  CalcDisclosure,
  Delta,
  FreshnessBar,
  GoalStatusBadge,
  SeverityBadge,
} from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

const PERIODS = ["1M", "3M", "YTD", "1Y", "3Y"];

export default function DashboardPage() {
  const { data, error, loading, refetch } = useApi<DashboardPayload>("/api/dashboard");
  const [period, setPeriod] = useState("YTD");

  return (
    <div className="space-y-8">
      <DataState
        loading={loading}
        error={error}
        data={data}
        onRetry={refetch}
        loadingFallback={
          <div className="space-y-6">
            <div className="h-8 w-64 skeleton rounded" />
            <LoadingGrid count={4} />
          </div>
        }
      >
        {(dashboard) => {
          const netWorth = dashboard.net_worth.result;
          const portfolio = dashboard.portfolio.result;
          const goals = dashboard.goals.result;
          const risk = dashboard.risk.result;
          const concentration = dashboard.concentration.result;
          const periodReturn = dashboard.performance.periods[period];

          const trend = dashboard.net_worth_trend.map((point) => ({
            as_of: point.as_of,
            value: point.net_worth,
          }));
          const firstNetWorth = trend[0]?.value ?? netWorth.net_worth;
          const trendChange = netWorth.net_worth - firstNetWorth;

          return (
            <>
              <PageHeader
                title={dashboard.household.name}
                description="Your complete financial picture, with every figure traceable to the calculation that produced it."
                meta={<FreshnessBar freshness={dashboard.data_freshness} asOf={dashboard.as_of} />}
                actions={
                  <>
                    <Link href="/reports">
                      <Button size="sm">Generate report</Button>
                    </Link>
                    <Link href="/wealthagent">
                      <Button variant="primary" size="sm">
                        <Sparkles />
                        Ask WealthAgent
                      </Button>
                    </Link>
                  </>
                }
              />

              {/* ------------------------------------------------ Headline */}
              <StatRow columns={4}>
                <StatTile
                  label="Net worth"
                  value={formatCurrency(netWorth.net_worth, { compact: true })}
                  delta={trendChange}
                  hint={`Since ${formatDate(dashboard.net_worth_trend[0]?.as_of, "medium")}`}
                  icon={TrendingUp}
                  tone="primary"
                />
                <StatTile
                  label="Total assets"
                  value={formatCurrency(netWorth.total_assets, { compact: true })}
                  hint={`Across ${Object.keys(netWorth.by_account_type).length} account types`}
                  icon={Wallet}
                  href="/accounts"
                />
                <StatTile
                  label="Total liabilities"
                  value={formatCurrency(netWorth.total_liabilities, { compact: true })}
                  hint={`Leverage ratio ${formatPercent(netWorth.leverage_ratio, { decimals: 1 })}`}
                  icon={Scale}
                  href="/accounts"
                />
                <StatTile
                  label="Portfolio value"
                  value={formatCurrency(portfolio.market_value, { compact: true })}
                  delta={portfolio.day_change}
                  deltaPercent={portfolio.day_change_percent}
                  hint="Change today"
                  icon={Layers}
                  href="/portfolio"
                />
              </StatRow>

              {/* -------------------------------------- Net worth + agent */}
              <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
                <Card>
                  <CardHeader
                    title="Net worth over time"
                    description="Assets less liabilities, derived from the portfolio series and current balances."
                  />
                  <CardBody>
                    <TrendArea data={trend} label="Net worth" height={248} />
                    <div className="mt-5 border-t border-border pt-4">
                      <KeyValue
                        columns={3}
                        items={[
                          { label: "Unrealised gain", value: formatCurrency(portfolio.unrealized_gain, { compact: true }) },
                          { label: "Gain on cost", value: formatPercent(portfolio.unrealized_gain_percent, { decimals: 1 }) },
                          { label: "Cash held", value: formatCurrency(portfolio.cash, { compact: true }) },
                        ]}
                      />
                      <CalcDisclosure calculation={dashboard.net_worth} className="mt-4" />
                    </div>
                  </CardBody>
                </Card>

                <WealthAgentPanel dashboard={dashboard} />
              </div>

              {/* ------------------------------------- Portfolio + attention */}
              <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
                <Card>
                  <CardHeader
                    title="Portfolio performance"
                    description={
                      dashboard.performance.benchmark
                        ? `Against ${dashboard.performance.benchmark.name}, both rebased to 100.`
                        : "Time-weighted return."
                    }
                    action={<SegmentedControl options={PERIODS.map((p) => ({ value: p, label: p }))} value={period} onChange={setPeriod} />}
                  />
                  <CardBody>
                    <div className="grid grid-cols-3 gap-4 pb-5">
                      <Metric label={`${period} return`} value={formatPercent(periodReturn?.return, { signed: true })} tone={periodReturn?.return >= 0 ? "positive" : "negative"} />
                      <Metric label="Benchmark" value={formatPercent(periodReturn?.benchmark_return, { signed: true })} />
                      <Metric
                        label="Excess"
                        value={formatPercent(periodReturn?.excess_return, { signed: true })}
                        tone={periodReturn?.excess_return >= 0 ? "positive" : "negative"}
                      />
                    </div>
                    <IndexedComparison
                      data={dashboard.performance.series.slice(-260)}
                      benchmarkName={dashboard.performance.benchmark?.name ?? "Benchmark"}
                      height={220}
                    />
                  </CardBody>
                </Card>

                <NeedsAttention dashboard={dashboard} />
              </div>

              {/* ------------------------------------------- Allocation etc */}
              <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
                <Card>
                  <CardHeader
                    title="Asset allocation"
                    description="Every position grouped by asset class, including cash held in managed accounts."
                    action={
                      <Link href="/portfolio">
                        <Button variant="ghost" size="sm">
                          Detail <ChevronRight />
                        </Button>
                      </Link>
                    }
                  />
                  <CardBody>
                    <AllocationDonut
                      data={dashboard.allocation.result.rows.map((row) => ({
                        label: row.label,
                        value: row.market_value,
                        weight: row.weight,
                      }))}
                      centerLabel="Portfolio"
                      centerValue={formatCurrency(dashboard.allocation.result.total, { compact: true })}
                    />
                    <CalcDisclosure calculation={dashboard.allocation} className="mt-5 border-t border-border pt-4" />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="Risk & concentration" description="How much of the outcome rests on how few things." />
                  <CardBody className="space-y-5">
                    <KeyValue
                      items={[
                        { label: "Portfolio beta", value: risk.beta.toFixed(2) },
                        { label: "Estimated volatility", value: formatPercent(risk.volatility, { decimals: 1 }) },
                        { label: "Equity exposure", value: formatPercent(risk.equity_exposure, { decimals: 1 }) },
                        { label: "Cash exposure", value: formatPercent(risk.cash_exposure, { decimals: 1 }) },
                        { label: "Top five holdings", value: formatPercent(concentration.top_five_weight, { decimals: 1 }) },
                        {
                          label: "Largest single name",
                          value: concentration.top_single_name
                            ? `${concentration.top_single_name.symbol} · ${formatPercent(concentration.top_single_name.weight, { decimals: 1 })}`
                            : "None above threshold",
                        },
                      ]}
                    />
                    {concentration.flagged.length > 0 ? (
                      <div className="rounded-md border border-warning/25 bg-warning-soft px-3.5 py-3">
                        <p className="text-xs font-semibold text-warning">Above the policy guideline</p>
                        <ul className="mt-1.5 space-y-1">
                          {concentration.flagged.map((row) => (
                            <li key={row.symbol} className="flex justify-between text-xs text-ink">
                              <span>
                                {row.symbol} · {row.name}
                              </span>
                              <span className="tabular font-medium">{formatPercent(row.weight, { decimals: 1 })}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <CalcDisclosure calculation={dashboard.risk} />
                  </CardBody>
                </Card>
              </div>

              {/* ----------------------------------------------------- Goals */}
              <Section
                title="Goals"
                description={`${goals.goal_count} goals tracked · ${formatCurrency(goals.total_current, { compact: true })} of ${formatCurrency(goals.total_target, { compact: true })} funded`}
                actions={
                  <Link href="/goals">
                    <Button variant="ghost" size="sm">
                      All goals <ChevronRight />
                    </Button>
                  </Link>
                }
              >
                {goals.goals.length === 0 ? (
                  <Card>
                    <EmptyState icon={Target} title="No goals set up yet" description="Add a goal to start tracking progress." />
                  </Card>
                ) : (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {goals.goals.map((goal) => {
                      const tone =
                        goal.status === "on_track"
                          ? "positive"
                          : goal.status === "off_track"
                            ? "negative"
                            : goal.status === "at_risk"
                              ? "warning"
                              : "primary";
                      return (
                        <Link key={goal.id} href={`/goals/${goal.id}`} className="block">
                          <Card className="h-full p-5 transition-shadow hover:shadow-raised">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-ink">{goal.name}</p>
                                <p className="mt-0.5 text-xs text-ink-muted">
                                  Target {formatDate(goal.target_date)} · {goal.years_to_target} yrs
                                </p>
                              </div>
                              <GoalStatusBadge status={goal.status} />
                            </div>

                            <div className="mt-4 flex items-baseline justify-between gap-2">
                              <span className="text-lg font-semibold tabular text-ink">
                                {formatCurrency(goal.current_amount, { compact: true })}
                              </span>
                              <span className="text-xs text-ink-muted">
                                of {formatCurrency(goal.target_amount, { compact: true })}
                              </span>
                            </div>

                            <Progress value={goal.progress_percent} tone={tone} className="mt-3" showTrackLabel />

                            <dl className="mt-4 space-y-1.5 border-t border-border pt-3 text-xs">
                              <div className="flex justify-between">
                                <dt className="text-ink-muted">Projected at target date</dt>
                                <dd className="tabular font-medium text-ink">
                                  {formatCurrency(goal.projected_value, { compact: true })}
                                </dd>
                              </div>
                              <div className="flex justify-between">
                                <dt className="text-ink-muted">Funded ratio</dt>
                                <dd className="tabular font-medium text-ink">{formatPercent(goal.funded_ratio, { decimals: 0 })}</dd>
                              </div>
                              {goal.additional_monthly_needed > 0 ? (
                                <div className="flex justify-between">
                                  <dt className="text-ink-muted">Additional monthly needed</dt>
                                  <dd className="tabular font-medium text-warning">
                                    {formatCurrency(goal.additional_monthly_needed)}
                                  </dd>
                                </div>
                              ) : null}
                            </dl>
                          </Card>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </Section>

              {/* ----------------------------------------- Holdings + meeting */}
              <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
                <Card>
                  <CardHeader
                    title="Largest holdings"
                    action={
                      <Link href="/holdings">
                        <Button variant="ghost" size="sm">
                          All holdings <ChevronRight />
                        </Button>
                      </Link>
                    }
                  />
                  <ul className="divide-y divide-border">
                    {dashboard.top_holdings.map((holding) => (
                      <li key={holding.holding_id} className="flex items-center justify-between gap-4 px-5 py-3">
                        <div className="min-w-0">
                          <p className="flex items-center gap-2 text-sm font-medium text-ink">
                            {holding.symbol}
                            <Badge tone="outline" size="sm">
                              {holding.asset_class_label}
                            </Badge>
                          </p>
                          <p className="mt-0.5 truncate text-xs text-ink-muted">{holding.name}</p>
                        </div>
                        <div className="shrink-0 text-right">
                          <p className="text-sm font-medium tabular text-ink">
                            {formatCurrency(holding.market_value, { compact: true })}
                          </p>
                          <div className="mt-0.5 flex items-center justify-end gap-2">
                            <span className="text-xs tabular text-ink-subtle">
                              {formatPercent(holding.weight, { decimals: 1 })}
                            </span>
                            <Delta percent={holding.gain_loss_percent} showIcon={false} />
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </Card>

                <div className="space-y-6">
                  {dashboard.next_meeting ? (
                    <Card>
                      <CardHeader title="Next review" />
                      <CardBody>
                        <p className="text-sm font-semibold text-ink">{dashboard.next_meeting.title}</p>
                        <p className="mt-1 flex items-center gap-1.5 text-xs text-ink-muted">
                          <CalendarDays className="size-3.5" aria-hidden />
                          {formatDateTime(dashboard.next_meeting.starts_at)}
                        </p>
                        {dashboard.next_meeting.agenda?.length ? (
                          <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
                            {dashboard.next_meeting.agenda.slice(0, 4).map((item) => (
                              <li key={item} className="flex gap-2 text-xs text-ink-muted">
                                <span className="mt-1.5 size-1 shrink-0 rounded-full bg-ink-subtle" aria-hidden />
                                {item}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        <Link href="/meetings" className="mt-4 block">
                          <Button size="sm" className="w-full">
                            Meeting details
                          </Button>
                        </Link>
                      </CardBody>
                    </Card>
                  ) : null}

                  <Card>
                    <CardHeader title="Recent notifications" />
                    {dashboard.notifications.notifications.length === 0 ? (
                      <EmptyState title="Nothing new" description="You are all caught up." />
                    ) : (
                      <ul className="divide-y divide-border">
                        {dashboard.notifications.notifications.slice(0, 5).map((notification) => (
                          <li key={notification.id} className="px-5 py-3">
                            <div className="flex items-start gap-2">
                              <SeverityBadge severity={notification.severity} />
                              <div className="min-w-0">
                                <p className="text-sm font-medium leading-5 text-ink">{notification.title}</p>
                                <p className="mt-0.5 text-xs leading-5 text-ink-muted">{notification.body}</p>
                              </div>
                            </div>
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

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "positive" | "negative" }) {
  const toneClass = { neutral: "text-ink", positive: "text-positive", negative: "text-negative" }[tone];
  return (
    <div>
      <p className="section-label">{label}</p>
      <p className={`mt-1 text-lg font-semibold tabular ${toneClass}`}>{value}</p>
    </div>
  );
}

function NeedsAttention({ dashboard }: { dashboard: DashboardPayload }) {
  return (
    <Card>
      <CardHeader
        title="Needs attention"
        description="What the platform found in your data this morning, most important first."
        action={<Badge tone={dashboard.needs_attention.length ? "warning" : "positive"}>{dashboard.needs_attention.length} open</Badge>}
      />
      {dashboard.needs_attention.length === 0 ? (
        <EmptyState title="Nothing needs your attention" description="No portfolio, goal, tax or document issues were found." />
      ) : (
        <ul className="divide-y divide-border">
          {dashboard.needs_attention.map((item) => (
            <li key={item.key} className="px-5 py-3.5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={item.severity} />
                    <Badge tone="outline" size="sm">
                      {item.category}
                    </Badge>
                  </div>
                  <p className="mt-1.5 text-sm font-medium leading-5 text-ink">{item.title}</p>
                  <p className="mt-1 text-xs leading-5 text-ink-muted">{item.summary}</p>
                </div>
                {item.action_url ? (
                  <Link href={item.action_url} className="shrink-0">
                    <Button variant="ghost" size="icon-sm" aria-label={`Open ${item.title}`}>
                      <ArrowUpRight />
                    </Button>
                  </Link>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function WealthAgentPanel({ dashboard }: { dashboard: DashboardPayload }) {
  const { insights, actions, provider } = dashboard.wealthagent;

  return (
    <Card className="flex flex-col">
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" aria-hidden />
            WealthAgent
          </span>
        }
        description="Insights derived from your verified figures."
        action={<Badge tone="primary">{provider.mode === "mock" ? "Rules engine" : provider.name}</Badge>}
      />

      <CardBody className="flex-1 space-y-4">
        {insights.length === 0 ? (
          <EmptyState title="No insights right now" description="Nothing in your data crossed a review threshold." />
        ) : (
          insights.slice(0, 3).map((insight) => (
            <div key={insight.key} className="rounded-md border border-border bg-surface-muted/50 p-3.5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-semibold leading-5 text-ink">{insight.title}</p>
                <SeverityBadge severity={insight.severity} />
              </div>
              <p className="mt-1.5 text-xs leading-5 text-ink-muted">{insight.summary}</p>
              {insight.supporting_facts.length > 0 ? (
                <dl className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-2">
                  {insight.supporting_facts.slice(0, 3).map((fact) => (
                    <div key={fact.label} className="text-2xs">
                      <dt className="text-ink-subtle">{fact.label}</dt>
                      <dd className="font-medium tabular text-ink">{fact.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </div>
          ))
        )}
      </CardBody>

      {actions.length > 0 ? (
        <div className="border-t border-border px-5 py-4">
          <p className="section-label">Suggested next steps</p>
          <ul className="mt-2.5 space-y-1.5">
            {actions.slice(0, 3).map((action) => (
              <li key={action.key}>
                <Link
                  href={action.route}
                  className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-sm text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
                >
                  <span className="truncate">{action.label}</span>
                  <ChevronRight className="size-3.5 shrink-0" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
          <Link href="/wealthagent" className="mt-3 block">
            <Button variant="primary" size="sm" className="w-full">
              Open WealthAgent
              <ArrowRight />
            </Button>
          </Link>
        </div>
      ) : null}
    </Card>
  );
}
