"use client";

/** Plan costs (§32): fee benchmarking, revenue sharing and vendor scorecards. */

import { useState } from "react";
import { Coins, TrendingDown } from "lucide-react";

import { formatCurrency, formatDate, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Card, CardBody, CardHeader, Select, TD, TH, THead, TR, Table } from "@/components/ui";
import { CalcDisclosure } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingTable } from "@/components/shared/states";

type FeesPayload = {
  plan: { id: string; name: string; total_assets: number; participating_employees: number };
  as_of: string;
  benchmark: Calculation<{
    total_annual_cost: number;
    all_in_basis_points: number;
    per_participant_cost: number;
    participant_paid: number;
    sponsor_paid: number;
    total_savings_opportunity: number;
    lines: {
      vendor: string;
      fee_type: string;
      payer: string;
      annual_amount: number;
      basis_points: number;
      benchmark_basis_points: number;
      variance_bps: number;
      above_benchmark: boolean;
      annual_savings_opportunity: number;
      revenue_sharing: number;
    }[];
  }>;
  investment_costs: {
    weighted_expense_ratio: number;
    total_revenue_sharing: number;
    options: {
      name: string;
      ticker: string | null;
      expense_ratio: number;
      category_median_expense: number;
      plan_assets: number;
      revenue_share_bps: number;
      above_median: boolean;
    }[];
  };
  vendors: {
    id: string;
    vendor: string;
    fee_type: string;
    payer: string;
    annual_amount: number;
    per_participant_amount: number;
    basis_points: number;
    benchmark_basis_points: number;
    contract_end: string | null;
    sla_score: number | null;
    notes: string | null;
  }[];
};

export default function PlanFeesPage() {
  const { data: plans } = useApi<{ id: string; name: string }[]>("/api/plans");
  const [planId, setPlanId] = useState("");
  const suffix = planId ? `?plan_id=${planId}` : "";
  const { data, error, loading, refetch } = useApi<FeesPayload>(`/api/institutional/fees${suffix}`, [planId]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Plan costs"
        description="All-in cost against peer benchmarks, by payer and by vendor, with revenue sharing shown explicitly."
        actions={
          <Select
            value={planId}
            onChange={(event) => setPlanId(event.target.value)}
            className="h-9 w-64 text-xs"
            aria-label="Choose a plan"
          >
            <option value="">Default plan</option>
            {plans?.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name}
              </option>
            ))}
          </Select>
        }
      />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={6} />}>
        {(payload) => {
          const benchmark = payload.benchmark.result;

          return (
            <>
              <StatRow columns={4}>
                <StatTile
                  label="All-in cost"
                  value={`${benchmark.all_in_basis_points.toFixed(1)} bp`}
                  hint={formatCurrency(benchmark.total_annual_cost, { compact: true })}
                  icon={Coins}
                  tone="primary"
                />
                <StatTile
                  label="Per participant"
                  value={formatCurrency(benchmark.per_participant_cost)}
                  hint={`${formatNumber(payload.plan.participating_employees)} participants`}
                />
                <StatTile
                  label="Participant paid"
                  value={formatCurrency(benchmark.participant_paid, { compact: true })}
                  hint={`Sponsor pays ${formatCurrency(benchmark.sponsor_paid, { compact: true })}`}
                />
                <StatTile
                  label="Savings opportunity"
                  value={formatCurrency(benchmark.total_savings_opportunity, { compact: true })}
                  hint="Against peer benchmarks"
                  tone={benchmark.total_savings_opportunity > 0 ? "warning" : "positive"}
                  icon={TrendingDown}
                />
              </StatRow>

              <Card>
                <CardHeader title="Fee benchmarking" description="Each fee line against a peer plan of similar size." />
                <Table>
                  <THead>
                    <TR>
                      <TH>Vendor</TH>
                      <TH>Service</TH>
                      <TH>Paid by</TH>
                      <TH align="right">Annual</TH>
                      <TH align="right">Basis points</TH>
                      <TH align="right">Benchmark</TH>
                      <TH align="right">Variance</TH>
                      <TH align="right">Revenue sharing</TH>
                      <TH align="right">Opportunity</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {benchmark.lines.map((line) => (
                      <TR key={`${line.vendor}-${line.fee_type}`}>
                        <TD className="font-medium">{line.vendor}</TD>
                        <TD className="text-xs">{titleCase(line.fee_type)}</TD>
                        <TD>
                          <Badge tone={line.payer === "participant" ? "warning" : "outline"} size="sm">
                            {titleCase(line.payer)}
                          </Badge>
                        </TD>
                        <TD align="right" numeric>{formatCurrency(line.annual_amount, { compact: true })}</TD>
                        <TD align="right" numeric className="font-medium">{line.basis_points.toFixed(1)}</TD>
                        <TD align="right" numeric className="text-ink-muted">{line.benchmark_basis_points.toFixed(1)}</TD>
                        <TD
                          align="right"
                          numeric
                          className={cn("font-medium", line.above_benchmark ? "text-warning" : "text-positive")}
                        >
                          {line.variance_bps > 0 ? "+" : ""}
                          {line.variance_bps.toFixed(1)}
                        </TD>
                        <TD align="right" numeric className="text-ink-muted">
                          {line.revenue_sharing > 0 ? formatCurrency(line.revenue_sharing, { compact: true }) : "—"}
                        </TD>
                        <TD align="right" numeric className={line.annual_savings_opportunity > 0 ? "font-medium text-warning" : "text-ink-subtle"}>
                          {line.annual_savings_opportunity > 0 ? formatCurrency(line.annual_savings_opportunity, { compact: true }) : "—"}
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
                <CardBody>
                  <CalcDisclosure calculation={payload.benchmark} />
                </CardBody>
              </Card>

              <div className="grid gap-6 xl:grid-cols-2">
                <Card>
                  <CardHeader title="Investment costs" description="Expense ratios against category medians." />
                  <CardBody className="space-y-4">
                    <KeyValue
                      items={[
                        { label: "Weighted expense ratio", value: formatPercent(payload.investment_costs.weighted_expense_ratio, { decimals: 3 }) },
                        { label: "Total revenue sharing", value: formatCurrency(payload.investment_costs.total_revenue_sharing, { compact: true }) },
                      ]}
                    />
                    <div className="scroll-x rounded-md border border-border">
                      <Table>
                        <THead>
                          <TR>
                            <TH>Fund</TH>
                            <TH align="right">Expense</TH>
                            <TH align="right">Median</TH>
                            <TH align="right">Rev share</TH>
                          </TR>
                        </THead>
                        <tbody>
                          {payload.investment_costs.options.map((option) => (
                            <TR key={option.name}>
                              <TD>
                                <span className="font-medium">{option.name}</span>
                                <span className="mt-0.5 block text-xs text-ink-muted">
                                  {option.ticker} · {formatCurrency(option.plan_assets, { compact: true })}
                                </span>
                              </TD>
                              <TD align="right" numeric className={option.above_median ? "font-medium text-warning" : ""}>
                                {formatPercent(option.expense_ratio, { decimals: 2 })}
                              </TD>
                              <TD align="right" numeric className="text-ink-muted">
                                {formatPercent(option.category_median_expense, { decimals: 2 })}
                              </TD>
                              <TD align="right" numeric className="text-ink-muted">
                                {option.revenue_share_bps > 0 ? `${option.revenue_share_bps} bp` : "—"}
                              </TD>
                            </TR>
                          ))}
                        </tbody>
                      </Table>
                    </div>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="Vendor scorecards" description="Contract terms and service levels." />
                  <ul className="divide-y divide-border">
                    {payload.vendors.map((vendor) => (
                      <li key={vendor.id} className="px-5 py-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
                              {vendor.vendor}
                              <Badge tone="outline" size="sm">{titleCase(vendor.fee_type)}</Badge>
                            </p>
                            {vendor.notes ? <p className="mt-0.5 text-xs text-ink-muted">{vendor.notes}</p> : null}
                          </div>
                          {vendor.sla_score !== null ? (
                            <Badge tone={vendor.sla_score >= 4.5 ? "positive" : vendor.sla_score >= 4 ? "primary" : "warning"}>
                              SLA {vendor.sla_score.toFixed(1)}/5
                            </Badge>
                          ) : null}
                        </div>
                        <KeyValue
                          className="mt-3"
                          columns={2}
                          items={[
                            { label: "Annual cost", value: formatCurrency(vendor.annual_amount, { compact: true }) },
                            { label: "Per participant", value: formatCurrency(vendor.per_participant_amount) },
                            { label: "Basis points", value: `${vendor.basis_points.toFixed(1)} bp` },
                            { label: "Contract ends", value: vendor.contract_end ? formatDate(vendor.contract_end) : "—" },
                          ]}
                        />
                      </li>
                    ))}
                  </ul>
                </Card>
              </div>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
