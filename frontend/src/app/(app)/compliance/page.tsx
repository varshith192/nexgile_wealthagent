"use client";

/** Compliance centre (§31): tests, filings, deadlines and evidence. */

import { useState } from "react";
import { CalendarClock, CircleCheck, FileCheck2, Play, TriangleAlert } from "lucide-react";

import { api } from "@/lib/api";
import { formatDate, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Dialog, Select, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { CalcDisclosure, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type ComplianceTest = {
  id: string;
  test_type: string;
  tax_year: number;
  hce_value: number | null;
  nhce_value: number | null;
  threshold: number | null;
  result: string;
  status: string;
  due_date: string | null;
  completed_on: string | null;
  corrective_action: string | null;
  method: string;
  has_evidence: boolean;
};

type Filing = {
  id: string;
  filing_type: string;
  tax_year: number;
  due_date: string;
  extended_due_date: string | null;
  filed_on: string | null;
  status: string;
  preparer: string | null;
  auditor: string | null;
  notes: string | null;
};

type CompliancePayload = {
  plan_id: string;
  as_of: string;
  tests: ComplianceTest[];
  filings: Filing[];
  counts: Record<string, number>;
  next_deadline: string | null;
};

export default function CompliancePage() {
  const { data: plans } = useApi<{ id: string; name: string }[]>("/api/plans");
  const [planId, setPlanId] = useState("");
  const suffix = planId ? `?plan_id=${planId}` : "";
  const { data, error, loading, refetch } = useApi<CompliancePayload>(`/api/compliance${suffix}`, [planId]);
  const [tab, setTab] = useState("tests");
  const [result, setResult] = useState<{ test: ComplianceTest; calculation: Calculation<Record<string, any>> } | null>(null);

  const { run: runTest, pending } = useMutation(async (test: ComplianceTest) => {
    const payload = await api.post<{ test_id: string; calculation: Calculation<Record<string, any>> }>(
      `/api/compliance/tests/${test.id}/run`,
    );
    setResult({ test, calculation: payload.calculation });
    refetch();
    return payload;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compliance center"
        description="Nondiscrimination testing, statutory filings and the evidence behind each one."
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
        {(compliance) => (
          <>
            <StatRow columns={4}>
              <StatTile label="Complete" value={String(compliance.counts.complete ?? 0)} tone="positive" icon={CircleCheck} />
              <StatTile label="Pending" value={String(compliance.counts.pending ?? 0)} icon={FileCheck2} />
              <StatTile
                label="At risk"
                value={String(compliance.counts.at_risk ?? 0)}
                tone={compliance.counts.at_risk ? "warning" : "default"}
                icon={TriangleAlert}
              />
              <StatTile
                label="Overdue"
                value={String(compliance.counts.overdue ?? 0)}
                tone={compliance.counts.overdue ? "negative" : "positive"}
              />
            </StatRow>

            {compliance.next_deadline ? (
              <Card className="border-warning/25 bg-warning-soft/40">
                <CardBody className="flex items-center gap-3 py-4">
                  <CalendarClock className="size-4 shrink-0 text-warning" aria-hidden />
                  <p className="text-sm text-ink">
                    Next deadline: <span className="font-semibold">{formatDate(compliance.next_deadline, "long")}</span>
                  </p>
                </CardBody>
              </Card>
            ) : null}

            <Card>
              <div className="px-5 pt-4">
                <Tabs
                  value={tab}
                  onChange={setTab}
                  tabs={[
                    { value: "tests", label: "Tests", count: compliance.tests.length },
                    { value: "filings", label: "Filings", count: compliance.filings.length },
                  ]}
                />
              </div>

              {tab === "tests" ? (
                compliance.tests.length === 0 ? (
                  <EmptyState title="No tests configured" />
                ) : (
                  <Table>
                    <THead>
                      <TR>
                        <TH>Test</TH>
                        <TH>Year</TH>
                        <TH align="right">HCE</TH>
                        <TH align="right">NHCE</TH>
                        <TH align="right">Threshold</TH>
                        <TH>Result</TH>
                        <TH>Due</TH>
                        <TH align="right">Status</TH>
                        <TH align="right"> </TH>
                      </TR>
                    </THead>
                    <tbody>
                      {compliance.tests.map((test) => {
                        const isRatio = test.test_type.toLowerCase().includes("adp") || test.test_type.toLowerCase().includes("acp");
                        const runnable = isRatio || test.test_type.toLowerCase().includes("top");
                        return (
                          <TR key={test.id}>
                            <TD>
                              <span className="font-medium">{test.test_type}</span>
                              <span className="mt-0.5 block text-xs text-ink-muted">{titleCase(test.method)}</span>
                              {test.corrective_action ? (
                                <span className="mt-1 block max-w-[22rem] text-2xs text-warning">{test.corrective_action}</span>
                              ) : null}
                            </TD>
                            <TD className="tabular text-xs">{test.tax_year}</TD>
                            <TD align="right" numeric className="text-xs">
                              {test.hce_value === null ? "—" : isRatio ? formatPercent(test.hce_value, { decimals: 2 }) : test.hce_value.toLocaleString()}
                            </TD>
                            <TD align="right" numeric className="text-xs">
                              {test.nhce_value === null ? "—" : isRatio ? formatPercent(test.nhce_value, { decimals: 2 }) : test.nhce_value.toLocaleString()}
                            </TD>
                            <TD align="right" numeric className="text-xs text-ink-muted">
                              {test.threshold === null ? "—" : test.threshold < 1 ? formatPercent(test.threshold, { decimals: 2 }) : test.threshold.toLocaleString()}
                            </TD>
                            <TD><StatusBadge status={test.result} /></TD>
                            <TD className="whitespace-nowrap text-xs text-ink-muted">
                              {test.due_date ? formatDate(test.due_date) : "—"}
                              {test.completed_on ? (
                                <span className="mt-0.5 block text-2xs text-positive">Completed {formatDate(test.completed_on)}</span>
                              ) : null}
                            </TD>
                            <TD align="right">
                              <span className="flex items-center justify-end gap-1.5">
                                <StatusBadge status={test.status} />
                                {test.has_evidence ? <Badge tone="outline" size="sm">Evidence</Badge> : null}
                              </span>
                            </TD>
                            <TD align="right">
                              {runnable ? (
                                <Button size="sm" variant="ghost" loading={pending} onClick={() => runTest(test)}>
                                  <Play />
                                  Run
                                </Button>
                              ) : null}
                            </TD>
                          </TR>
                        );
                      })}
                    </tbody>
                  </Table>
                )
              ) : compliance.filings.length === 0 ? (
                <EmptyState title="No filings tracked" />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Filing</TH>
                      <TH>Year</TH>
                      <TH>Due</TH>
                      <TH>Extended</TH>
                      <TH>Filed</TH>
                      <TH>Preparer</TH>
                      <TH align="right">Status</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {compliance.filings.map((filing) => (
                      <TR key={filing.id}>
                        <TD>
                          <span className="font-medium">{titleCase(filing.filing_type)}</span>
                          {filing.notes ? (
                            <span className="mt-0.5 block max-w-[24rem] text-xs text-ink-muted">{filing.notes}</span>
                          ) : null}
                        </TD>
                        <TD className="tabular text-xs">{filing.tax_year}</TD>
                        <TD className="whitespace-nowrap text-xs">{formatDate(filing.due_date)}</TD>
                        <TD className="whitespace-nowrap text-xs text-ink-muted">
                          {filing.extended_due_date ? formatDate(filing.extended_due_date) : "—"}
                        </TD>
                        <TD className="whitespace-nowrap text-xs">
                          {filing.filed_on ? (
                            <span className="text-positive">{formatDate(filing.filed_on)}</span>
                          ) : (
                            <span className="text-ink-subtle">Not filed</span>
                          )}
                        </TD>
                        <TD className="text-xs text-ink-muted">
                          {filing.preparer ?? "—"}
                          {filing.auditor ? <span className="mt-0.5 block text-2xs">Audit: {filing.auditor}</span> : null}
                        </TD>
                        <TD align="right"><StatusBadge status={filing.status} /></TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>
          </>
        )}
      </DataState>

      <Dialog
        open={Boolean(result)}
        onClose={() => setResult(null)}
        title={result ? `${result.test.test_type} test result` : "Test result"}
        description={result ? `Tax year ${result.test.tax_year}` : undefined}
        footer={
          <Button size="sm" onClick={() => setResult(null)}>
            Close
          </Button>
        }
      >
        {result ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <StatusBadge status={result.calculation.result.result} />
              {result.calculation.result.is_top_heavy !== undefined ? (
                <Badge tone={result.calculation.result.is_top_heavy ? "negative" : "positive"}>
                  {result.calculation.result.is_top_heavy ? "Top heavy" : "Not top heavy"}
                </Badge>
              ) : null}
            </div>

            <KeyValue
              items={Object.entries(result.calculation.result)
                .filter(([, value]) => typeof value === "number" || typeof value === "string")
                .map(([key, value]) => ({
                  label: titleCase(key),
                  value: typeof value === "number" && value < 1 && value > 0 ? formatPercent(value, { decimals: 2 }) : String(value),
                }))}
            />

            {result.calculation.result.corrective_action ? (
              <div className="rounded-md border border-warning/25 bg-warning-soft px-3.5 py-3">
                <p className="text-xs font-semibold text-warning">Corrective action</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-muted">{result.calculation.result.corrective_action}</p>
              </div>
            ) : null}

            <CalcDisclosure calculation={result.calculation} />
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
