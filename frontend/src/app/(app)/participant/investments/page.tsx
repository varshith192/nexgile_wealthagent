"use client";

/** The investment menu available in the participant's plan. */

import { formatPercent } from "@/lib/format";
import type { ParticipantPortal } from "@/lib/participant";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardBody, CardHeader, TD, TH, THead, TR, Table } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { PageHeader } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

export default function ParticipantInvestmentsPage() {
  const { data, error, loading, refetch } = useApi<ParticipantPortal>("/api/participant");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Investments"
        description="The menu your plan offers, with costs and how each option has performed."
      />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={6} />}>
        {(portal) => (
          <>
            <Card className="border-info/25 bg-info-soft/40">
              <CardBody className="py-4">
                <p className="text-sm font-medium text-ink">Not sure where to start?</p>
                <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                  The option marked QDIA is your plan&rsquo;s default: a single fund that holds a diversified mix and
                  becomes more conservative as your target retirement year approaches. Cost matters — a lower expense
                  ratio leaves more of the return with you.
                </p>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Investment menu" description={`${portal.investments.length} options in ${portal.plan.name}.`} />
              {portal.investments.length === 0 ? (
                <EmptyState title="No investment options listed" />
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Fund</TH>
                      <TH>Category</TH>
                      <TH align="right">Expense ratio</TH>
                      <TH align="right">3-year return</TH>
                      <TH align="right">5-year return</TH>
                      <TH align="right">Monitoring</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {portal.investments.map((option) => (
                      <TR key={option.id}>
                        <TD>
                          <span className="flex items-center gap-2 font-medium">
                            {option.name}
                            {option.is_qdia ? <Badge tone="primary" size="sm">Default (QDIA)</Badge> : null}
                          </span>
                          <span className="mt-0.5 block text-xs text-ink-muted">{option.ticker}</span>
                        </TD>
                        <TD className="text-xs">{option.asset_category}</TD>
                        <TD align="right" numeric>{formatPercent(option.expense_ratio, { decimals: 2 })}</TD>
                        <TD align="right" numeric>{formatPercent(option.three_year_return, { decimals: 2 })}</TD>
                        <TD align="right" numeric className="text-ink-muted">{formatPercent(option.five_year_return, { decimals: 2 })}</TD>
                        <TD align="right"><StatusBadge status={option.ips_status} /></TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              )}
              <CardBody>
                <p className="text-xs leading-relaxed text-ink-subtle">
                  Monitoring status reflects the investment committee&rsquo;s review against the plan&rsquo;s investment
                  policy statement. A fund on watch remains available; it is simply under closer review. Past
                  performance does not predict future returns.
                </p>
              </CardBody>
            </Card>
          </>
        )}
      </DataState>
    </div>
  );
}
