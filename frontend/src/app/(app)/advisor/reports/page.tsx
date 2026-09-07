"use client";

/** Advisor reporting: generate a pack for any household in the book. */

import { useState } from "react";
import Link from "next/link";
import { FileBarChart } from "lucide-react";

import { api } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/format";
import { useApi, useMutation } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, Field, Input, Select } from "@/components/ui";
import { PageHeader } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type ReportsPayload = {
  reports: {
    id: string;
    report_label: string;
    title: string;
    period_start: string;
    period_end: string;
    status: string;
    generated_at: string | null;
  }[];
  catalogue: { key: string; label: string; description: string; sections: string[] }[];
};

function isoDaysAgo(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

export default function AdvisorReportsPage() {
  const { data: clients } = useApi<{ clients: { household_id: string; name: string }[] }>("/api/advisor/clients");
  const [householdId, setHouseholdId] = useState("");
  const suffix = householdId ? `?household_id=${householdId}` : "";
  const { data, error, loading, refetch } = useApi<ReportsPayload>(`/api/reports${suffix}`, [householdId]);

  const [reportType, setReportType] = useState("quarterly_review");
  const [periodStart, setPeriodStart] = useState(isoDaysAgo(90));
  const [periodEnd, setPeriodEnd] = useState(new Date().toISOString().slice(0, 10));

  const { run: generate, pending, message } = useMutation(async () => {
    const created = await api.post("/api/reports", {
      report_type: reportType,
      period_start: periodStart,
      period_end: periodEnd,
      household_id: householdId || undefined,
    });
    refetch();
    return created;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Reports"
        description="Produce a dated pack for any household. Open the Reports page to preview the full document."
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

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={5} />}>
        {(payload) => (
          <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
            <Card>
              <CardHeader title="Generate" />
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
              <CardHeader
                title="Recent reports"
                description={`${payload.reports.length} on record`}
                action={
                  <Link href="/reports">
                    <Button variant="ghost" size="sm">
                      Preview
                    </Button>
                  </Link>
                }
              />
              {payload.reports.length === 0 ? (
                <EmptyState title="No reports yet" description="Generate one to see it here." />
              ) : (
                <ul className="divide-y divide-border">
                  {payload.reports.map((report) => (
                    <li key={report.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
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
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        )}
      </DataState>
    </div>
  );
}
