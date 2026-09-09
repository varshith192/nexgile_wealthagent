"use client";

/**
 * Client 360 (§21).
 *
 * Everything an advisor needs about one household, on one screen: profile,
 * household, accounts, portfolio, goals, tax, estate, documents, messages,
 * meetings, tasks, recommendations and the full activity timeline.
 */

import { use, useState } from "react";
import Link from "next/link";
import {
  Activity,
  BadgeCheck,
  CalendarDays,
  FileText,
  Lightbulb,
  MessageSquare,
  Radar,
  Receipt,
  Scale,
  Target,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatDateTime, formatPercent, titleCase } from "@/lib/format";
import type { AccountRow, Calculation, GoalRow, PerformancePayload } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Progress, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { AllocationDonut, DivergingBars, IndexedComparison } from "@/components/charts";
import { CalcDisclosure, Delta, FreshnessBadge, GoalStatusBadge, SeverityBadge, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type Client360 = {
  as_of: string;
  household: {
    id: string;
    name: string;
    segment: string;
    risk_profile: string;
    since: string | null;
    city: string | null;
    state: string | null;
    notes: string | null;
  };
  profile: {
    id: string;
    full_name: string;
    birth_date: string | null;
    age: number | null;
    retirement_age: number;
    filing_status: string;
    marginal_tax_rate: number;
    annual_income: number;
    annual_savings: number;
    risk_tolerance: string;
    status: string;
    segment: string;
  }[];
  household_members: { id: string; full_name: string; relationship: string; birth_date: string | null; is_dependent: boolean }[];
  team: { advisor_id: string; name: string; role_on_account: string; is_primary: boolean }[];
  accounts: {
    accounts: AccountRow[];
    summary: { total_assets: number; total_liabilities: number; net_worth: number; account_count: number; external_count: number };
  };
  net_worth: Calculation<{ total_assets: number; total_liabilities: number; net_worth: number; leverage_ratio: number }>;
  portfolio: {
    valuation: Calculation<{ market_value: number; cost_basis: number; unrealized_gain: number; unrealized_gain_percent: number; day_change: number; day_change_percent: number; cash: number }>;
    allocation: Calculation<{ total: number; rows: { key: string; label: string; market_value: number; weight: number }[] }>;
    drift: Calculation<{ rows: { asset_class: string; label: string; drift: number; tolerance_band: number; breached: boolean }[]; max_drift: number; breach_count: number }>;
    concentration: Calculation<{ top_single_name: { symbol: string; weight: number } | null; top_five_weight: number; hhi: number; flagged: { symbol: string; weight: number }[] }>;
    risk: Calculation<{ beta: number; volatility: number; equity_exposure: number; cash_exposure: number }>;
    performance: PerformancePayload;
  };
  goals: Calculation<{ goals: GoalRow[]; total_target: number; total_current: number; overall_progress: number; goals_off_track: number; goal_count: number }>;
  tax: {
    harvest: Calculation<{ opportunities: { symbol: string; unrealized_loss: number; estimated_tax_benefit: number }[]; opportunity_count: number; total_estimated_benefit: number }>;
    opportunities: { id: string; title: string; opportunity_type: string; estimated_benefit: number; severity: string; status: string; deadline: string | null }[];
  };
  estate: {
    projection: Calculation<{ gross_estate: number; estimated_federal_tax: number; net_to_heirs: number }>;
    beneficiary_gaps: { account_id: string; account_name: string; reason: string; balance: number }[];
    trusts: { id: string; name: string; trust_type: string; funded_amount: number; status: string }[];
    last_reviewed_on: string | null;
  };
  documents: { id: string; name: string; category: string; review_status: string; uploaded_at: string }[];
  messages: { id: string; subject: string; topic: string; status: string; last_message_at: string | null; message_count: number }[];
  meetings: { id: string; title: string; meeting_type: string; starts_at: string; status: string; agenda: string[]; summary: string | null }[];
  tasks: { id: string; title: string; status: string; priority: string; category: string; due_date: string | null }[];
  recommendations: { id: string; title: string; category: string; severity: string; status: string; summary: string; impact_amount: number | null; created_at: string }[];
  activity: {
    id: string;
    action: string;
    entity_type: string;
    entity_label: string | null;
    actor_name: string;
    actor_role: string | null;
    status: string;
    summary: string | null;
    created_at: string;
  }[];
};

export default function Client360Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, loading, refetch } = useApi<Client360>(`/api/advisor/clients/${id}`);
  const [tab, setTab] = useState("overview");

  const { run: proposeRebalance, pending: rebalancing } = useMutation(async () => {
    const created = await api.post<{ id: string }>("/api/advisor/rebalancing", { household_id: id });
    refetch();
    return created;
  });

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(client) => {
          const netWorth = client.net_worth.result;
          const valuation = client.portfolio.valuation.result;
          const goals = client.goals.result;
          const primary = client.profile[0];

          return (
            <>
              <PageHeader
                breadcrumb={[{ label: "Clients", href: "/advisor/clients" }, { label: client.household.name }]}
                title={client.household.name}
                description={client.household.notes ?? undefined}
                meta={
                  <>
                    <Badge tone="outline">{titleCase(client.household.segment)}</Badge>
                    <Badge tone="outline">{titleCase(client.household.risk_profile)} risk</Badge>
                    {client.household.city ? (
                      <Badge tone="outline">
                        {client.household.city}, {client.household.state}
                      </Badge>
                    ) : null}
                    {client.household.since ? (
                      <span className="text-xs text-ink-muted">Client since {formatDate(client.household.since)}</span>
                    ) : null}
                    <span className="text-xs text-ink-muted">· As of {formatDate(client.as_of)}</span>
                  </>
                }
                actions={
                  <>
                    <Button size="sm" loading={rebalancing} onClick={() => proposeRebalance()}>
                      <Activity />
                      Propose rebalance
                    </Button>
                    <Link href={`/wealthagent?household_id=${id}`}>
                      <Button variant="primary" size="sm">
                        <Radar />
                        WealthAgent
                      </Button>
                    </Link>
                  </>
                }
              />

              <StatRow columns={5}>
                <StatTile label="Net worth" value={formatCurrency(netWorth.net_worth, { compact: true })} icon={TrendingUp} tone="primary" />
                <StatTile label="Portfolio" value={formatCurrency(valuation.market_value, { compact: true })} delta={valuation.day_change} icon={Wallet} />
                <StatTile
                  label="Goals"
                  value={`${goals.goal_count - goals.goals_off_track}/${goals.goal_count}`}
                  hint="On plan"
                  tone={goals.goals_off_track ? "warning" : "positive"}
                  icon={Target}
                />
                <StatTile
                  label="Tax opportunity"
                  value={formatCurrency(client.tax.harvest.result.total_estimated_benefit, { compact: true })}
                  hint={`${client.tax.harvest.result.opportunity_count} candidates`}
                  icon={Receipt}
                />
                <StatTile
                  label="Estate tax estimate"
                  value={formatCurrency(client.estate.projection.result.estimated_federal_tax, { compact: true })}
                  hint={`Estate ${formatCurrency(client.estate.projection.result.gross_estate, { compact: true })}`}
                  icon={Scale}
                />
              </StatRow>

              <Card>
                <div className="px-5 pt-4">
                  <Tabs
                    value={tab}
                    onChange={setTab}
                    tabs={[
                      { value: "overview", label: "Overview" },
                      { value: "household", label: "Household", count: client.profile.length + client.household_members.length },
                      { value: "accounts", label: "Accounts", count: client.accounts.summary.account_count },
                      { value: "portfolio", label: "Portfolio" },
                      { value: "goals", label: "Goals", count: goals.goal_count },
                      { value: "tax", label: "Tax", count: client.tax.opportunities.length },
                      { value: "estate", label: "Estate" },
                      { value: "service", label: "Service", count: client.tasks.length + client.messages.length },
                      { value: "recommendations", label: "Recommendations", count: client.recommendations.length },
                      { value: "activity", label: "Activity", count: client.activity.length },
                    ]}
                  />
                </div>

                <CardBody className="space-y-6">
                  {tab === "overview" ? <Overview client={client} /> : null}
                  {tab === "household" ? <Household client={client} /> : null}
                  {tab === "accounts" ? <Accounts client={client} /> : null}
                  {tab === "portfolio" ? <Portfolio client={client} /> : null}
                  {tab === "goals" ? <Goals client={client} /> : null}
                  {tab === "tax" ? <Tax client={client} /> : null}
                  {tab === "estate" ? <Estate client={client} /> : null}
                  {tab === "service" ? <Service client={client} /> : null}
                  {tab === "recommendations" ? <Recommendations client={client} /> : null}
                  {tab === "activity" ? <Timeline client={client} /> : null}
                </CardBody>
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}

/* ------------------------------------------------------------- Overview */

function Overview({ client }: { client: Client360 }) {
  const performance = client.portfolio.performance.periods.YTD;
  const drift = client.portfolio.drift.result;
  const risk = client.portfolio.risk.result;

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <div className="space-y-5">
        <div>
          <p className="section-label">Performance year to date</p>
          <div className="mt-2 grid grid-cols-3 gap-3">
            <Metric label="Portfolio" value={formatPercent(performance?.return, { signed: true })} tone={performance?.return >= 0 ? "positive" : "negative"} />
            <Metric label="Benchmark" value={formatPercent(performance?.benchmark_return, { signed: true })} />
            <Metric label="Excess" value={formatPercent(performance?.excess_return, { signed: true })} tone={performance?.excess_return >= 0 ? "positive" : "negative"} />
          </div>
        </div>
        <IndexedComparison
          data={client.portfolio.performance.series.slice(-260)}
          benchmarkName={client.portfolio.performance.benchmark?.name ?? "Benchmark"}
          height={200}
        />
      </div>

      <div className="space-y-5">
        <div>
          <p className="section-label">Allocation</p>
          <div className="mt-2">
            <AllocationDonut
              data={client.portfolio.allocation.result.rows.map((row) => ({
                label: row.label,
                value: row.market_value,
                weight: row.weight,
              }))}
              height={190}
            />
          </div>
        </div>

        <KeyValue
          items={[
            { label: "Portfolio beta", value: risk.beta.toFixed(2) },
            { label: "Estimated volatility", value: formatPercent(risk.volatility, { decimals: 1 }) },
            { label: "Bands breached", value: String(drift.breach_count) },
            { label: "Maximum drift", value: formatPercent(drift.max_drift, { decimals: 1 }) },
            {
              label: "Largest single name",
              value: client.portfolio.concentration.result.top_single_name
                ? `${client.portfolio.concentration.result.top_single_name.symbol} · ${formatPercent(client.portfolio.concentration.result.top_single_name.weight, { decimals: 1 })}`
                : "None",
            },
            { label: "Top five weight", value: formatPercent(client.portfolio.concentration.result.top_five_weight, { decimals: 1 }) },
          ]}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ Household */

function Household({ client }: { client: Client360 }) {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div>
        <p className="section-label">Principals</p>
        <ul className="mt-2.5 space-y-3">
          {client.profile.map((person) => (
            <li key={person.id} className="rounded-lg border border-border p-4">
              <p className="text-sm font-semibold text-ink">{person.full_name}</p>
              <p className="mt-0.5 text-xs text-ink-muted">
                {person.age ? `Age ${person.age}` : "Age not recorded"} · retires at {person.retirement_age}
              </p>
              <KeyValue
                className="mt-3"
                columns={1}
                items={[
                  { label: "Filing status", value: titleCase(person.filing_status) },
                  { label: "Marginal rate", value: formatPercent(person.marginal_tax_rate, { decimals: 0 }) },
                  { label: "Annual income", value: formatCurrency(person.annual_income, { compact: true }) },
                  { label: "Annual savings", value: formatCurrency(person.annual_savings, { compact: true }) },
                  { label: "Risk tolerance", value: titleCase(person.risk_tolerance) },
                ]}
              />
            </li>
          ))}
        </ul>
      </div>

      <div>
        <p className="section-label">Family</p>
        <ul className="mt-2.5 space-y-2">
          {client.household_members.map((member) => (
            <li key={member.id} className="flex items-center justify-between gap-3 rounded-md border border-border px-3.5 py-2.5">
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{member.full_name}</span>
                <span className="block text-xs text-ink-muted">
                  {titleCase(member.relationship)}
                  {member.is_dependent ? " · dependent" : ""}
                </span>
              </span>
              <span className="shrink-0 text-xs text-ink-muted">
                {member.birth_date ? formatDate(member.birth_date) : "—"}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <p className="section-label">Advisory team</p>
        <ul className="mt-2.5 space-y-2">
          {client.team.map((member) => (
            <li key={`${member.advisor_id}-${member.role_on_account}`} className="flex items-center justify-between gap-3 rounded-md border border-border px-3.5 py-2.5">
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-ink">{member.name}</span>
                <span className="block text-xs text-ink-muted">{titleCase(member.role_on_account)}</span>
              </span>
              {member.is_primary ? <Badge tone="primary" size="sm">Lead</Badge> : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- Accounts */

function Accounts({ client }: { client: Client360 }) {
  return (
    <div className="space-y-4">
      <KeyValue
        columns={3}
        items={[
          { label: "Total assets", value: formatCurrency(client.accounts.summary.total_assets, { compact: true }) },
          { label: "Total liabilities", value: formatCurrency(client.accounts.summary.total_liabilities, { compact: true }) },
          { label: "Net worth", value: formatCurrency(client.accounts.summary.net_worth, { compact: true }) },
        ]}
      />
      <div className="scroll-x rounded-md border border-border">
        <Table>
          <THead>
            <TR>
              <TH>Account</TH>
              <TH>Institution</TH>
              <TH>Type</TH>
              <TH>Tax treatment</TH>
              <TH align="right">Balance</TH>
              <TH align="right">Data</TH>
            </TR>
          </THead>
          <tbody>
            {client.accounts.accounts.map((account) => (
              <TR key={account.id}>
                <TD>
                  <Link href={`/accounts/${account.id}`} className="font-medium text-ink hover:text-primary">
                    {account.name}
                  </Link>
                  <span className="mt-0.5 block text-xs text-ink-muted">{account.account_number_masked}</span>
                </TD>
                <TD className="text-xs">{account.institution}</TD>
                <TD><Badge tone="outline" size="sm">{titleCase(account.account_type)}</Badge></TD>
                <TD className="text-xs text-ink-muted">{titleCase(account.tax_treatment)}</TD>
                <TD align="right" numeric className={cn("font-medium", account.is_liability && "text-negative")}>
                  {account.is_liability ? "−" : ""}
                  {formatCurrency(account.balance, { compact: true })}
                </TD>
                <TD align="right"><FreshnessBadge status={account.data_freshness} /></TD>
              </TR>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ Portfolio */

function Portfolio({ client }: { client: Client360 }) {
  const valuation = client.portfolio.valuation.result;
  const drift = client.portfolio.drift.result;

  return (
    <div className="space-y-6">
      <KeyValue
        columns={3}
        items={[
          { label: "Market value", value: formatCurrency(valuation.market_value, { compact: true }) },
          { label: "Cost basis", value: formatCurrency(valuation.cost_basis, { compact: true }) },
          { label: "Unrealised gain", value: formatCurrency(valuation.unrealized_gain, { compact: true }) },
          { label: "Cash", value: formatCurrency(valuation.cash, { compact: true }) },
          { label: "Change today", value: formatCurrency(valuation.day_change, { compact: true, signed: true }) },
          { label: "Concentration index", value: client.portfolio.concentration.result.hhi.toFixed(3) },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-2">
        <div>
          <p className="section-label">Allocation</p>
          <div className="mt-2.5">
            <AllocationDonut
              data={client.portfolio.allocation.result.rows.map((row) => ({
                label: row.label,
                value: row.market_value,
                weight: row.weight,
              }))}
              height={210}
            />
          </div>
        </div>
        <div>
          <p className="section-label">Drift against policy</p>
          <div className="mt-2.5">
            <DivergingBars
              data={drift.rows.map((row) => ({ label: row.label, value: row.drift, band: row.tolerance_band }))}
              height={Math.max(180, drift.rows.length * 32)}
            />
          </div>
        </div>
      </div>

      <CalcDisclosure calculation={client.portfolio.valuation} />
    </div>
  );
}

/* ---------------------------------------------------------------- Goals */

function Goals({ client }: { client: Client360 }) {
  const goals = client.goals.result;
  if (goals.goals.length === 0) return <EmptyState icon={Target} title="No goals recorded" />;

  return (
    <div className="space-y-4">
      <KeyValue
        columns={3}
        items={[
          { label: "Total target", value: formatCurrency(goals.total_target, { compact: true }) },
          { label: "Currently funded", value: formatCurrency(goals.total_current, { compact: true }) },
          { label: "Overall progress", value: formatPercent(goals.overall_progress, { decimals: 0 }) },
        ]}
      />
      <div className="scroll-x rounded-md border border-border">
        <Table>
          <THead>
            <TR>
              <TH>Goal</TH>
              <TH>Target date</TH>
              <TH align="right">Current</TH>
              <TH align="right">Target</TH>
              <TH align="right">Projected</TH>
              <TH align="right">Funded</TH>
              <TH align="right">Additional needed</TH>
              <TH align="right">Status</TH>
            </TR>
          </THead>
          <tbody>
            {goals.goals.map((goal) => (
              <TR key={goal.id}>
                <TD>
                  <Link href={`/goals/${goal.id}`} className="font-medium text-ink hover:text-primary">
                    {goal.name}
                  </Link>
                  <span className="mt-0.5 block text-xs text-ink-muted">{titleCase(goal.goal_type)}</span>
                </TD>
                <TD className="whitespace-nowrap text-xs">{formatDate(goal.target_date)}</TD>
                <TD align="right" numeric>{formatCurrency(goal.current_amount, { compact: true })}</TD>
                <TD align="right" numeric className="text-ink-muted">{formatCurrency(goal.target_amount, { compact: true })}</TD>
                <TD align="right" numeric>{formatCurrency(goal.projected_value, { compact: true })}</TD>
                <TD align="right">
                  <span className="tabular text-sm">{formatPercent(goal.funded_ratio, { decimals: 0 })}</span>
                  <Progress value={goal.progress_percent} tone={goal.status === "on_track" ? "positive" : "warning"} className="mt-1 w-20" />
                </TD>
                <TD align="right" numeric className={goal.additional_monthly_needed > 0 ? "text-warning" : "text-ink-subtle"}>
                  {goal.additional_monthly_needed > 0 ? `${formatCurrency(goal.additional_monthly_needed)}/mo` : "—"}
                </TD>
                <TD align="right"><GoalStatusBadge status={goal.status} /></TD>
              </TR>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Tax */

function Tax({ client }: { client: Client360 }) {
  const harvest = client.tax.harvest.result;

  return (
    <div className="space-y-5">
      <KeyValue
        columns={3}
        items={[
          { label: "Harvest candidates", value: String(harvest.opportunity_count) },
          { label: "Estimated benefit", value: formatCurrency(harvest.total_estimated_benefit, { compact: true }) },
          { label: "Open opportunities", value: String(client.tax.opportunities.length) },
        ]}
      />

      {client.tax.opportunities.length > 0 ? (
        <ul className="space-y-2.5">
          {client.tax.opportunities.map((opportunity) => (
            <li key={opportunity.id} className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-border p-3.5">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={opportunity.severity as "low" | "medium" | "high"} />
                  <Badge tone="outline" size="sm">{titleCase(opportunity.opportunity_type)}</Badge>
                  <StatusBadge status={opportunity.status} />
                </div>
                <p className="mt-1.5 text-sm font-medium text-ink">{opportunity.title}</p>
                {opportunity.deadline ? (
                  <p className="mt-0.5 text-2xs text-ink-subtle">Deadline {formatDate(opportunity.deadline)}</p>
                ) : null}
              </div>
              <p className="shrink-0 text-sm font-semibold tabular text-positive">
                {formatCurrency(opportunity.estimated_benefit, { compact: true })}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState icon={Receipt} title="No open tax opportunities" />
      )}

      {harvest.opportunities.length > 0 ? (
        <div className="scroll-x rounded-md border border-border">
          <Table>
            <THead>
              <TR>
                <TH>Security</TH>
                <TH align="right">Unrealised loss</TH>
                <TH align="right">Estimated benefit</TH>
              </TR>
            </THead>
            <tbody>
              {harvest.opportunities.map((row, index) => (
                <TR key={`${row.symbol}-${index}`}>
                  <TD className="font-medium">{row.symbol}</TD>
                  <TD align="right" numeric className="text-negative">{formatCurrency(row.unrealized_loss)}</TD>
                  <TD align="right" numeric className="font-medium text-positive">{formatCurrency(row.estimated_tax_benefit)}</TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </div>
      ) : null}

      <CalcDisclosure calculation={client.tax.harvest} />
    </div>
  );
}

/* --------------------------------------------------------------- Estate */

function Estate({ client }: { client: Client360 }) {
  const projection = client.estate.projection.result;

  return (
    <div className="space-y-5">
      <KeyValue
        columns={3}
        items={[
          { label: "Gross estate", value: formatCurrency(projection.gross_estate, { compact: true }) },
          { label: "Estimated federal tax", value: formatCurrency(projection.estimated_federal_tax, { compact: true }) },
          { label: "Net to heirs", value: formatCurrency(projection.net_to_heirs, { compact: true }) },
          { label: "Last reviewed", value: client.estate.last_reviewed_on ? formatDate(client.estate.last_reviewed_on) : "—" },
          { label: "Trusts", value: String(client.estate.trusts.length) },
          { label: "Beneficiary gaps", value: String(client.estate.beneficiary_gaps.length) },
        ]}
      />

      {client.estate.beneficiary_gaps.length > 0 ? (
        <div className="rounded-md border border-warning/25 bg-warning-soft/40 p-3.5">
          <p className="text-sm font-semibold text-warning">Beneficiary designations need attention</p>
          <ul className="mt-2 space-y-1.5">
            {client.estate.beneficiary_gaps.map((gap) => (
              <li key={gap.account_id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
                <span className="font-medium text-ink">{gap.account_name}</span>
                <span className="text-ink-muted">{gap.reason}</span>
                <span className="tabular font-medium text-ink">{formatCurrency(gap.balance, { compact: true })}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {client.estate.trusts.length > 0 ? (
        <div className="scroll-x rounded-md border border-border">
          <Table>
            <THead>
              <TR>
                <TH>Trust</TH>
                <TH>Type</TH>
                <TH align="right">Funded</TH>
                <TH align="right">Status</TH>
              </TR>
            </THead>
            <tbody>
              {client.estate.trusts.map((trust) => (
                <TR key={trust.id}>
                  <TD className="font-medium">{trust.name}</TD>
                  <TD className="text-xs">{titleCase(trust.trust_type)}</TD>
                  <TD align="right" numeric>{formatCurrency(trust.funded_amount, { compact: true })}</TD>
                  <TD align="right"><StatusBadge status={trust.status} /></TD>
                </TR>
              ))}
            </tbody>
          </Table>
        </div>
      ) : null}

      <CalcDisclosure calculation={client.estate.projection} />
    </div>
  );
}

/* -------------------------------------------------------------- Service */

function Service({ client }: { client: Client360 }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-4">
      <Panel title="Tasks" icon={BadgeCheck} empty="No open tasks">
        {client.tasks.map((task) => (
          <li key={task.id} className="px-3.5 py-2.5">
            <p className="text-sm font-medium leading-5 text-ink">{task.title}</p>
            <p className="mt-0.5 flex items-center gap-2 text-2xs text-ink-subtle">
              <StatusBadge status={task.status} />
              {task.due_date ? `due ${formatDate(task.due_date)}` : "no due date"}
            </p>
          </li>
        ))}
      </Panel>

      <Panel title="Messages" icon={MessageSquare} empty="No conversations">
        {client.messages.map((thread) => (
          <li key={thread.id} className="px-3.5 py-2.5">
            <p className="text-sm font-medium leading-5 text-ink">{thread.subject}</p>
            <p className="mt-0.5 text-2xs text-ink-subtle">
              {thread.message_count} messages
              {thread.last_message_at ? ` · ${formatDate(thread.last_message_at)}` : ""}
            </p>
          </li>
        ))}
      </Panel>

      <Panel title="Meetings" icon={CalendarDays} empty="No meetings">
        {client.meetings.map((meeting) => (
          <li key={meeting.id} className="px-3.5 py-2.5">
            <p className="text-sm font-medium leading-5 text-ink">{meeting.title}</p>
            <p className="mt-0.5 text-2xs text-ink-subtle">
              {formatDate(meeting.starts_at)} · {titleCase(meeting.status)}
            </p>
          </li>
        ))}
      </Panel>

      <Panel title="Documents" icon={FileText} empty="No documents">
        {client.documents.map((document) => (
          <li key={document.id} className="px-3.5 py-2.5">
            <p className="truncate text-sm font-medium leading-5 text-ink">{document.name}</p>
            <p className="mt-0.5 flex items-center gap-2 text-2xs text-ink-subtle">
              <Badge tone="outline" size="sm">{titleCase(document.category)}</Badge>
              {formatDate(document.uploaded_at)}
            </p>
          </li>
        ))}
      </Panel>
    </div>
  );
}

function Panel({
  title,
  icon: Icon,
  empty,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  empty: string;
  children: React.ReactNode;
}) {
  const items = Array.isArray(children) ? children : [children];
  return (
    <div className="rounded-lg border border-border">
      <p className="flex items-center gap-1.5 border-b border-border px-3.5 py-2.5 text-2xs font-semibold uppercase tracking-[0.08em] text-ink-subtle">
        <Icon className="size-3.5" />
        {title}
      </p>
      {items.length === 0 ? (
        <p className="px-3.5 py-6 text-center text-xs text-ink-subtle">{empty}</p>
      ) : (
        <ul className="divide-y divide-border">{children}</ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------ Recommendations */

function Recommendations({ client }: { client: Client360 }) {
  if (client.recommendations.length === 0) {
    return <EmptyState icon={Lightbulb} title="No recommendations raised" description="Raise one from the WealthAgent workspace." />;
  }

  return (
    <ul className="space-y-3">
      {client.recommendations.map((recommendation) => (
        <li key={recommendation.id} className="rounded-lg border border-border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={recommendation.status} />
                <SeverityBadge severity={recommendation.severity as "low" | "medium" | "high"} />
                <Badge tone="outline" size="sm">{titleCase(recommendation.category)}</Badge>
              </div>
              <p className="mt-2 text-sm font-semibold text-ink">{recommendation.title}</p>
              <p className="mt-1 text-sm leading-6 text-ink-muted">{recommendation.summary}</p>
              <p className="mt-1.5 text-2xs text-ink-subtle">Raised {formatDate(recommendation.created_at)}</p>
            </div>
            {recommendation.impact_amount !== null ? (
              <p className="shrink-0 text-right text-base font-semibold tabular text-ink">
                {formatCurrency(recommendation.impact_amount, { compact: true })}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------- Timeline */

function Timeline({ client }: { client: Client360 }) {
  if (client.activity.length === 0) {
    return <EmptyState icon={Activity} title="No activity recorded" description="Actions on this household will appear here." />;
  }

  return (
    <ol className="space-y-0">
      {client.activity.map((event, index) => (
        <li key={event.id} className="relative flex gap-4 pb-5 last:pb-0">
          {index < client.activity.length - 1 ? (
            <span className="absolute left-[0.4375rem] top-4 h-full w-px bg-border" aria-hidden />
          ) : null}
          <span
            className={cn(
              "relative mt-1 size-3.5 shrink-0 rounded-full border-2 border-surface",
              event.status === "failed" ? "bg-negative" : "bg-primary",
            )}
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="outline" size="sm">{titleCase(event.action)}</Badge>
              <Badge tone="outline" size="sm">{titleCase(event.entity_type)}</Badge>
            </div>
            <p className="mt-1.5 text-sm leading-5 text-ink">
              {event.summary ?? `${titleCase(event.action)} — ${event.entity_label ?? event.entity_type}`}
            </p>
            <p className="mt-0.5 text-xs text-ink-muted">
              <span className="font-medium text-ink">{event.actor_name}</span>
              {event.actor_role ? ` (${titleCase(event.actor_role)})` : ""} · {formatDateTime(event.created_at)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "positive" | "negative" }) {
  const toneClass = { neutral: "text-ink", positive: "text-positive", negative: "text-negative" }[tone];
  return (
    <div className="rounded-md border border-border bg-surface-muted/60 p-3">
      <p className="section-label">{label}</p>
      <p className={cn("mt-1 text-base font-semibold tabular", toneClass)}>{value}</p>
    </div>
  );
}
