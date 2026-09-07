"use client";

/** Reports (§25): generate a dated pack and preview it in place. */

import { useState } from "react";
import { ClipboardList, Download, FileBarChart, Printer } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatDateTime, formatPercent, titleCase } from "@/lib/format";
import { useApi, useMutation } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, Field, Input, Select, TD, TH, THead, TR, Table } from "@/components/ui";
import { PageHeader, Section, KeyValue } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type ReportSummary = {
  id: string;
  report_type: string;
  report_label: string;
  title: string;
  period_start: string;
  period_end: string;
  benchmark_code: string | null;
  status: string;
  sections: string[];
  assumptions: string[];
  generated_at: string | null;
};

type ReportDetail = ReportSummary & { payload: Record<string, any> };

type ReportsPayload = {
  reports: ReportSummary[];
  catalogue: { key: string; label: string; description: string; sections: string[] }[];
};

function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const { data, error, loading, refetch } = useApi<ReportsPayload>("/api/reports");
  const [reportType, setReportType] = useState("quarterly_review");
  const [periodStart, setPeriodStart] = useState(isoDaysAgo(90));
  const [periodEnd, setPeriodEnd] = useState(new Date().toISOString().slice(0, 10));
  const [preview, setPreview] = useState<ReportDetail | null>(null);

  const { run: generate, pending, message } = useMutation(async () => {
    const created = await api.post<ReportDetail>("/api/reports", {
      report_type: reportType,
      period_start: periodStart,
      period_end: periodEnd,
    });
    setPreview(created);
    refetch();
    return created;
  });

  const { run: open, pending: opening } = useMutation(async (id: string) => {
    const detail = await api.get<ReportDetail>(`/api/reports/${id}`);
    setPreview(detail);
    return detail;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Dated, reproducible packs. The same period always renders the same figures, and every section carries its assumptions."
      />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={5} />}>
        {(payload) => (
          <>
            <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
              <Card>
                <CardHeader title="Generate a report" description="Pick a type and a period." />
                <CardBody className="space-y-4">
                  <Field label="Report type">
                    <Select value={reportType} onChange={(event) => setReportType(event.target.value)}>
                      {payload.catalogue.map((entry) => (
                        <option key={entry.key} value={entry.key}>
                          {entry.label}
                        </option>
                      ))}
                    </Select>
                  </Field>

                  <p className="text-xs leading-relaxed text-ink-muted">
                    {payload.catalogue.find((entry) => entry.key === reportType)?.description}
                  </p>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Period start">
                      <Input type="date" value={periodStart} onChange={(event) => setPeriodStart(event.target.value)} />
                    </Field>
                    <Field label="Period end">
                      <Input type="date" value={periodEnd} onChange={(event) => setPeriodEnd(event.target.value)} />
                    </Field>
                  </div>

                  <div>
                    <p className="section-label">Sections included</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {payload.catalogue
                        .find((entry) => entry.key === reportType)
                        ?.sections.map((section) => (
                          <Badge key={section} tone="outline">
                            {section}
                          </Badge>
                        ))}
                    </div>
                  </div>

                  {message ? (
                    <p role="alert" className="rounded-md border border-negative/25 bg-negative-soft px-3 py-2 text-sm text-negative">
                      {message}
                    </p>
                  ) : null}

                  <Button variant="primary" className="w-full" loading={pending} onClick={() => generate()}>
                    <FileBarChart />
                    Generate report
                  </Button>
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="Generated reports" description={`${payload.reports.length} on record`} />
                {payload.reports.length === 0 ? (
                  <EmptyState icon={ClipboardList} title="No reports yet" description="Generate one to see it here." />
                ) : (
                  <ul className="divide-y divide-border">
                    {payload.reports.map((report) => (
                      <li key={report.id}>
                        <button
                          onClick={() => open(report.id)}
                          disabled={opening}
                          className="flex w-full items-center justify-between gap-4 px-5 py-3.5 text-left transition-colors hover:bg-surface-muted/70 disabled:opacity-60"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-ink">{report.title}</p>
                            <p className="mt-0.5 text-xs text-ink-muted">
                              {formatDate(report.period_start)} – {formatDate(report.period_end)}
                              {report.generated_at ? ` · generated ${formatDate(report.generated_at)}` : ""}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <Badge tone="outline">{report.report_label}</Badge>
                            <Badge tone="positive">{titleCase(report.status)}</Badge>
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>

            {preview ? <ReportPreview report={preview} onClose={() => setPreview(null)} /> : null}
          </>
        )}
      </DataState>
    </div>
  );
}

function ReportPreview({ report, onClose }: { report: ReportDetail; onClose: () => void }) {
  const payload = report.payload ?? {};

  return (
    <Section
      title="Report preview"
      actions={
        <>
          <Button size="sm" onClick={() => window.print()} className="no-print">
            <Printer />
            Print
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose} className="no-print">
            Close
          </Button>
        </>
      }
    >
      <Card>
        <div className="border-b border-border px-6 py-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-2xs font-semibold uppercase tracking-[0.12em] text-primary">Nexgile WealthAgent</p>
              <h2 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">{report.title}</h2>
              <p className="mt-1 text-sm text-ink-muted">
                {formatDate(report.period_start, "long")} – {formatDate(report.period_end, "long")}
                {payload.as_of ? ` · figures as of ${formatDate(payload.as_of, "long")}` : ""}
              </p>
            </div>
            <div className="text-right text-xs text-ink-muted">
              <p>Prepared {report.generated_at ? formatDateTime(report.generated_at) : "—"}</p>
              {report.benchmark_code ? <p className="mt-0.5">Benchmark: {report.benchmark_code}</p> : null}
            </div>
          </div>
        </div>

        <CardBody className="space-y-8">
          {payload.net_worth ? (
            <ReportSection title="Net worth">
              <KeyValue
                columns={3}
                items={[
                  { label: "Total assets", value: formatCurrency(payload.net_worth.result.total_assets, { compact: true }) },
                  { label: "Total liabilities", value: formatCurrency(payload.net_worth.result.total_liabilities, { compact: true }) },
                  { label: "Net worth", value: formatCurrency(payload.net_worth.result.net_worth, { compact: true }) },
                ]}
              />
            </ReportSection>
          ) : null}

          {payload.valuation ? (
            <ReportSection title="Portfolio summary">
              <KeyValue
                columns={3}
                items={[
                  { label: "Market value", value: formatCurrency(payload.valuation.result.market_value, { compact: true }) },
                  { label: "Cost basis", value: formatCurrency(payload.valuation.result.cost_basis, { compact: true }) },
                  { label: "Unrealised gain", value: formatCurrency(payload.valuation.result.unrealized_gain, { compact: true }) },
                ]}
              />
            </ReportSection>
          ) : null}

          {payload.performance?.periods ? (
            <ReportSection title="Performance">
              <div className="scroll-x rounded-md border border-border">
                <Table>
                  <THead>
                    <TR>
                      <TH>Period</TH>
                      <TH align="right">Portfolio</TH>
                      <TH align="right">Benchmark</TH>
                      <TH align="right">Excess</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {Object.entries(payload.performance.periods).map(([period, row]) => {
                      const value = row as { return: number; benchmark_return: number; excess_return: number };
                      return (
                        <TR key={period}>
                          <TD className="font-medium">{period}</TD>
                          <TD align="right" numeric>{formatPercent(value.return, { signed: true })}</TD>
                          <TD align="right" numeric className="text-ink-muted">{formatPercent(value.benchmark_return, { signed: true })}</TD>
                          <TD align="right" numeric className={value.excess_return >= 0 ? "text-positive" : "text-negative"}>
                            {formatPercent(value.excess_return, { signed: true })}
                          </TD>
                        </TR>
                      );
                    })}
                  </tbody>
                </Table>
              </div>
            </ReportSection>
          ) : null}

          {payload.allocation?.result?.rows ? (
            <ReportSection title="Allocation">
              <div className="scroll-x rounded-md border border-border">
                <Table>
                  <THead>
                    <TR>
                      <TH>Asset class</TH>
                      <TH align="right">Market value</TH>
                      <TH align="right">Weight</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {payload.allocation.result.rows.map((row: { key: string; label: string; market_value: number; weight: number }) => (
                      <TR key={row.key}>
                        <TD className="font-medium">{row.label}</TD>
                        <TD align="right" numeric>{formatCurrency(row.market_value, { compact: true })}</TD>
                        <TD align="right" numeric>{formatPercent(row.weight, { decimals: 1 })}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </div>
            </ReportSection>
          ) : null}

          {payload.holdings ? (
            <ReportSection title="Holdings">
              <div className="scroll-x rounded-md border border-border">
                <Table>
                  <THead>
                    <TR>
                      <TH>Security</TH>
                      <TH align="right">Quantity</TH>
                      <TH align="right">Market value</TH>
                      <TH align="right">Gain/loss</TH>
                      <TH align="right">Weight</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {payload.holdings.slice(0, 25).map((row: any) => (
                      <TR key={row.holding_id}>
                        <TD>
                          <span className="font-medium">{row.symbol}</span>
                          <span className="mt-0.5 block max-w-[16rem] truncate text-xs text-ink-muted">{row.name}</span>
                        </TD>
                        <TD align="right" numeric>{row.quantity}</TD>
                        <TD align="right" numeric>{formatCurrency(row.market_value)}</TD>
                        <TD align="right" numeric className={row.gain_loss >= 0 ? "text-positive" : "text-negative"}>
                          {formatCurrency(row.gain_loss, { signed: true })}
                        </TD>
                        <TD align="right" numeric>{formatPercent(row.weight, { decimals: 2 })}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </div>
            </ReportSection>
          ) : null}

          {payload.goals?.result?.goals ? (
            <ReportSection title="Goals">
              <div className="scroll-x rounded-md border border-border">
                <Table>
                  <THead>
                    <TR>
                      <TH>Goal</TH>
                      <TH align="right">Current</TH>
                      <TH align="right">Target</TH>
                      <TH align="right">Projected</TH>
                      <TH align="right">Funded</TH>
                      <TH>Status</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {payload.goals.result.goals.map((goal: any) => (
                      <TR key={goal.id}>
                        <TD className="font-medium">{goal.name}</TD>
                        <TD align="right" numeric>{formatCurrency(goal.current_amount, { compact: true })}</TD>
                        <TD align="right" numeric>{formatCurrency(goal.target_amount, { compact: true })}</TD>
                        <TD align="right" numeric>{formatCurrency(goal.projected_value, { compact: true })}</TD>
                        <TD align="right" numeric>{formatPercent(goal.funded_ratio, { decimals: 0 })}</TD>
                        <TD className="text-xs">{titleCase(goal.status)}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </div>
            </ReportSection>
          ) : null}

          {payload.tax?.realized_gains || payload.realized_gains ? (
            <ReportSection title="Tax">
              <KeyValue
                columns={3}
                items={[
                  {
                    label: "Short-term gain",
                    value: formatCurrency(
                      (payload.tax?.realized_gains ?? payload.realized_gains).result.short_term_gain,
                      { compact: true },
                    ),
                  },
                  {
                    label: "Long-term gain",
                    value: formatCurrency(
                      (payload.tax?.realized_gains ?? payload.realized_gains).result.long_term_gain,
                      { compact: true },
                    ),
                  },
                  {
                    label: "Net gain",
                    value: formatCurrency(
                      (payload.tax?.realized_gains ?? payload.realized_gains).result.net_gain,
                      { compact: true },
                    ),
                  },
                ]}
              />
            </ReportSection>
          ) : null}

          {payload.estate ? (
            <ReportSection title="Estate">
              <KeyValue
                columns={3}
                items={[
                  { label: "Gross estate", value: formatCurrency(payload.estate.result.gross_estate, { compact: true }) },
                  { label: "Estimated federal tax", value: formatCurrency(payload.estate.result.estimated_federal_tax, { compact: true }) },
                  { label: "Net to heirs", value: formatCurrency(payload.estate.result.net_to_heirs, { compact: true }) },
                ]}
              />
            </ReportSection>
          ) : null}

          <ReportSection title="Assumptions and limitations">
            <ul className="list-disc space-y-1.5 pl-4 text-sm leading-6 text-ink-muted">
              {report.assumptions.map((assumption) => (
                <li key={assumption}>{assumption}</li>
              ))}
            </ul>
            <p className="mt-4 border-t border-border pt-3 text-xs leading-relaxed text-ink-subtle">
              This report is produced by Nexgile WealthAgent from the positions and balances held in the platform on
              the stated as-of date. It is not a custodial statement and is not investment, tax or legal advice.
            </p>
          </ReportSection>
        </CardBody>
      </Card>
    </Section>
  );
}

function ReportSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="border-b border-border pb-2 text-sm font-semibold tracking-tight text-ink">{title}</h3>
      <div className="mt-3.5">{children}</div>
    </section>
  );
}
