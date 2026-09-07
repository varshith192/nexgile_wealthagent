"use client";

/** Fiduciary oversight (§30): IPS screening, watch list and committee evidence. */

import { useState } from "react";
import { ClipboardCheck, Landmark, TriangleAlert } from "lucide-react";

import { formatCurrency, formatDate, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Card, CardBody, CardHeader, Select, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { CalcDisclosure, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type LineupOption = {
  id: string;
  name: string;
  ticker: string | null;
  asset_category: string;
  three_year_return: number;
  benchmark_three_year: number;
  excess_return: number;
  peer_rank_percentile: number;
  expense_ratio: number;
  category_median_expense: number;
  plan_assets: number;
  participants_invested: number;
  is_qdia: boolean;
  ips_status: string;
  reasons: string[];
};

type InvestmentsPayload = {
  plan: { id: string; name: string; total_assets: number };
  as_of: string;
  monitor: Calculation<{
    options: LineupOption[];
    pass_count: number;
    watch_count: number;
    replace_count: number;
    compliant: boolean;
  }>;
  reviews: {
    id: string;
    title: string;
    review_period: string;
    held_on: string;
    attendees: string[];
    agenda: string[];
    minutes: string | null;
    decisions: string[];
    funds_on_watch: number;
    ips_compliant: boolean;
    status: string;
  }[];
};

export default function InvestmentsPage() {
  const { data: plans } = useApi<{ id: string; name: string }[]>("/api/plans");
  const [planId, setPlanId] = useState("");
  const suffix = planId ? `?plan_id=${planId}` : "";
  const { data, error, loading, refetch } = useApi<InvestmentsPayload>(`/api/institutional/investments${suffix}`, [planId]);
  const [tab, setTab] = useState("lineup");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Investment lineup"
        description="Every option screened against the investment policy statement, with the committee evidence behind each decision."
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

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={8} />}>
        {(payload) => {
          const monitor = payload.monitor.result;

          return (
            <>
              <StatRow columns={4}>
                <StatTile label="Options" value={String(monitor.options.length)} icon={Landmark} tone="primary" />
                <StatTile label="Meeting policy" value={String(monitor.pass_count)} tone="positive" />
                <StatTile label="On watch" value={String(monitor.watch_count)} tone={monitor.watch_count ? "warning" : "default"} icon={TriangleAlert} />
                <StatTile label="Replace candidates" value={String(monitor.replace_count)} tone={monitor.replace_count ? "negative" : "default"} />
              </StatRow>

              {!monitor.compliant ? (
                <Card className="border-warning/25 bg-warning-soft/40">
                  <CardBody className="flex items-start gap-3 py-4">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
                    <div>
                      <p className="text-sm font-semibold text-ink">
                        {monitor.watch_count + monitor.replace_count} option
                        {monitor.watch_count + monitor.replace_count === 1 ? "" : "s"} fall short of the IPS criteria
                      </p>
                      <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">
                        A watch status is a prompt for committee discussion, not an automatic replacement. The reasons
                        for each are shown in the table below.
                      </p>
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
                      { value: "lineup", label: "Lineup", count: monitor.options.length },
                      { value: "reviews", label: "Committee reviews", count: payload.reviews.length },
                    ]}
                  />
                </div>

                {tab === "lineup" ? (
                  <>
                    <Table>
                      <THead>
                        <TR>
                          <TH>Fund</TH>
                          <TH>Category</TH>
                          <TH align="right">3yr return</TH>
                          <TH align="right">Benchmark</TH>
                          <TH align="right">Excess</TH>
                          <TH align="right">Peer rank</TH>
                          <TH align="right">Expense</TH>
                          <TH align="right">Plan assets</TH>
                          <TH align="right">IPS</TH>
                        </TR>
                      </THead>
                      <tbody>
                        {monitor.options.map((option) => (
                          <TR key={option.id}>
                            <TD>
                              <span className="flex items-center gap-2 font-medium">
                                {option.name}
                                {option.is_qdia ? <Badge tone="primary" size="sm">QDIA</Badge> : null}
                              </span>
                              <span className="mt-0.5 block text-xs text-ink-muted">
                                {option.ticker} · {formatNumber(option.participants_invested)} participants
                              </span>
                              {option.reasons.length > 0 ? (
                                <ul className="mt-1 space-y-0.5">
                                  {option.reasons.map((reason) => (
                                    <li key={reason} className="max-w-[24rem] text-2xs text-warning">
                                      {reason}
                                    </li>
                                  ))}
                                </ul>
                              ) : null}
                            </TD>
                            <TD className="text-xs">{option.asset_category}</TD>
                            <TD align="right" numeric>{formatPercent(option.three_year_return, { decimals: 2 })}</TD>
                            <TD align="right" numeric className="text-ink-muted">
                              {formatPercent(option.benchmark_three_year, { decimals: 2 })}
                            </TD>
                            <TD
                              align="right"
                              numeric
                              className={cn("font-medium", option.excess_return >= 0 ? "text-positive" : "text-negative")}
                            >
                              {formatPercent(option.excess_return, { decimals: 2, signed: true })}
                            </TD>
                            <TD align="right" numeric className={option.peer_rank_percentile > 50 ? "text-warning" : ""}>
                              {option.peer_rank_percentile}th
                            </TD>
                            <TD align="right" numeric className={option.expense_ratio > option.category_median_expense ? "text-warning" : ""}>
                              {formatPercent(option.expense_ratio, { decimals: 2 })}
                              <span className="mt-0.5 block text-2xs text-ink-subtle">
                                median {formatPercent(option.category_median_expense, { decimals: 2 })}
                              </span>
                            </TD>
                            <TD align="right" numeric>{formatCurrency(option.plan_assets, { compact: true })}</TD>
                            <TD align="right"><StatusBadge status={option.ips_status} /></TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                    <CardBody>
                      <CalcDisclosure calculation={payload.monitor} label="How the IPS screen works" />
                    </CardBody>
                  </>
                ) : payload.reviews.length === 0 ? (
                  <EmptyState icon={ClipboardCheck} title="No committee reviews recorded" />
                ) : (
                  <CardBody className="space-y-4">
                    {payload.reviews.map((review) => (
                      <div key={review.id} className="rounded-lg border border-border p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-ink">{review.title}</p>
                            <p className="mt-0.5 text-xs text-ink-muted">
                              {review.review_period} · held {formatDate(review.held_on, "long")}
                            </p>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-1.5">
                            <StatusBadge status={review.status} />
                            <Badge tone={review.ips_compliant ? "positive" : "warning"}>
                              {review.ips_compliant ? "IPS compliant" : "IPS exceptions"}
                            </Badge>
                            {review.funds_on_watch > 0 ? (
                              <Badge tone="warning">{review.funds_on_watch} on watch</Badge>
                            ) : null}
                          </div>
                        </div>

                        <div className="mt-4 grid gap-5 lg:grid-cols-2">
                          <div>
                            <p className="section-label">Agenda</p>
                            <ol className="mt-1.5 space-y-1">
                              {review.agenda.map((item, index) => (
                                <li key={item} className="flex gap-2 text-xs leading-5 text-ink-muted">
                                  <span className="text-ink-subtle">{index + 1}.</span>
                                  {item}
                                </li>
                              ))}
                            </ol>
                          </div>
                          <div>
                            <p className="section-label">Decisions</p>
                            <ul className="mt-1.5 space-y-1">
                              {review.decisions.map((decision) => (
                                <li key={decision} className="flex gap-2 text-xs leading-5 text-ink-muted">
                                  <span className="mt-1.5 size-1 shrink-0 rounded-full bg-primary" aria-hidden />
                                  {decision}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>

                        {review.minutes ? (
                          <div className="mt-4 border-t border-border pt-3">
                            <p className="section-label">Minutes</p>
                            <p className="mt-1.5 text-sm leading-6 text-ink-muted">{review.minutes}</p>
                          </div>
                        ) : null}

                        {review.attendees.length > 0 ? (
                          <div className="mt-3 flex flex-wrap items-center gap-1.5">
                            <span className="text-2xs text-ink-subtle">Attendees:</span>
                            {review.attendees.map((attendee) => (
                              <Badge key={attendee} tone="outline" size="sm">
                                {attendee}
                              </Badge>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </CardBody>
                )}
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
