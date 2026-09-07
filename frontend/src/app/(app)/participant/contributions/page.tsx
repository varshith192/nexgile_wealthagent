"use client";

/** Participant contributions, match and catch-up capacity. */

import { formatCurrency, formatDate, formatPercent } from "@/lib/format";
import type { ParticipantPortal } from "@/lib/participant";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardBody, CardHeader, Progress, TD, TH, THead, TR, Table } from "@/components/ui";
import { StackedBars } from "@/components/charts";
import { CalcDisclosure } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

export default function ContributionsPage() {
  const { data, error, loading, refetch } = useApi<ParticipantPortal>("/api/participant");

  return (
    <div className="space-y-6">
      <PageHeader title="Contributions" description="What you put in, what your employer added, and how much room is left." />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(portal) => {
          const capacity = portal.contributions.capacity.result;
          const participant = portal.participant;

          return (
            <>
              <StatRow columns={4}>
                <StatTile label="Your contributions" value={formatCurrency(portal.contributions.ytd_employee)} hint="Year to date" tone="primary" />
                <StatTile label="Employer contributions" value={formatCurrency(portal.contributions.ytd_employer)} hint="Match and profit sharing" />
                <StatTile
                  label="Contribution rate"
                  value={formatPercent(participant.deferral_rate + participant.roth_deferral_rate, { decimals: 1 })}
                  hint={`${formatPercent(participant.deferral_rate, { decimals: 1 })} pre-tax · ${formatPercent(participant.roth_deferral_rate, { decimals: 1 })} Roth`}
                />
                <StatTile
                  label="Remaining room"
                  value={formatCurrency(capacity.remaining_capacity)}
                  hint={capacity.catchup_eligible ? "Includes catch-up" : "Standard limit"}
                  tone={capacity.remaining_capacity > 0 ? "warning" : "positive"}
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
                <Card>
                  <CardHeader title="By quarter" description="Split between your money and your employer's." />
                  <CardBody>
                    <StackedBars
                      data={portal.contributions.history.map((row) => ({
                        label: formatDate(row.period_end, "short"),
                        "Pre-tax": row.employee_pretax,
                        Roth: row.employee_roth,
                        "Catch-up": row.employee_catchup,
                        "Employer match": row.employer_match,
                        "Profit sharing": row.employer_profit_sharing,
                      }))}
                      keys={[
                        { key: "Pre-tax", label: "Pre-tax" },
                        { key: "Roth", label: "Roth" },
                        { key: "Catch-up", label: "Catch-up" },
                        { key: "Employer match", label: "Employer match" },
                        { key: "Profit sharing", label: "Profit sharing" },
                      ]}
                      height={260}
                    />
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader title="Annual limit" description="Statutory elective deferral limit for this plan year." />
                  <CardBody className="space-y-4">
                    <Progress
                      value={capacity.ytd_deferral / capacity.annual_limit}
                      tone={capacity.on_pace_to_max ? "positive" : "primary"}
                      showTrackLabel
                    />
                    <KeyValue
                      columns={1}
                      items={[
                        { label: "Annual limit", value: formatCurrency(capacity.annual_limit) },
                        { label: "Contributed to date", value: formatCurrency(capacity.ytd_deferral) },
                        { label: "Projected for the year", value: formatCurrency(capacity.projected_deferral) },
                        { label: "Remaining", value: formatCurrency(capacity.remaining_capacity) },
                        {
                          label: "Catch-up",
                          value: capacity.catchup_eligible ? `Eligible · ${formatCurrency(capacity.catchup_amount)}` : "From age 50",
                        },
                        { label: "Rate to max out", value: formatPercent(capacity.required_rate_to_max, { decimals: 1 }) },
                      ]}
                    />
                    <CalcDisclosure calculation={portal.contributions.capacity} />
                  </CardBody>
                </Card>
              </div>

              <Card>
                <CardHeader title="Contribution history" description="Every recorded period." />
                <Table>
                  <THead>
                    <TR>
                      <TH>Period ending</TH>
                      <TH align="right">Pre-tax</TH>
                      <TH align="right">Roth</TH>
                      <TH align="right">Catch-up</TH>
                      <TH align="right">Employer match</TH>
                      <TH align="right">Profit sharing</TH>
                      <TH align="right">Total</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {[...portal.contributions.history].reverse().map((row) => (
                      <TR key={row.period_end}>
                        <TD className="whitespace-nowrap font-medium">{formatDate(row.period_end)}</TD>
                        <TD align="right" numeric>{formatCurrency(row.employee_pretax)}</TD>
                        <TD align="right" numeric>{row.employee_roth > 0 ? formatCurrency(row.employee_roth) : "—"}</TD>
                        <TD align="right" numeric>{row.employee_catchup > 0 ? formatCurrency(row.employee_catchup) : "—"}</TD>
                        <TD align="right" numeric className="text-positive">{formatCurrency(row.employer_match)}</TD>
                        <TD align="right" numeric className="text-positive">{formatCurrency(row.employer_profit_sharing)}</TD>
                        <TD align="right" numeric className="font-medium">{formatCurrency(row.total)}</TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
