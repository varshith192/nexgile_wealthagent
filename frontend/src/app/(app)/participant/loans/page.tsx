"use client";

/** Participant plan loans. */

import { Info, Landmark } from "lucide-react";

import { formatCurrency, formatDate, formatPercent, titleCase } from "@/lib/format";
import type { ParticipantPortal } from "@/lib/participant";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardBody, CardHeader, Progress, TD, TH, THead, TR, Table } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

export default function ParticipantLoansPage() {
  const { data, error, loading, refetch } = useApi<ParticipantPortal>("/api/participant");

  return (
    <div className="space-y-6">
      <PageHeader title="Loans" description="Outstanding plan loans, their terms and what remains to repay." />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={3} />}>
        {(portal) => {
          const loans = portal.loans;
          const outstanding = loans.reduce((total, loan) => total + loan.outstanding_balance, 0);
          const original = loans.reduce((total, loan) => total + loan.original_amount, 0);

          return (
            <>
              {loans.length > 0 ? (
                <StatRow columns={3}>
                  <StatTile label="Loans outstanding" value={String(loans.length)} icon={Landmark} tone="primary" />
                  <StatTile label="Balance owed" value={formatCurrency(outstanding)} hint={`of ${formatCurrency(original)} borrowed`} />
                  <StatTile
                    label="Monthly repayment"
                    value={formatCurrency(loans.reduce((total, loan) => total + loan.payment_amount, 0))}
                    hint="Deducted from pay"
                  />
                </StatRow>
              ) : null}

              <Card className="border-info/25 bg-info-soft/40">
                <CardBody className="flex gap-3 py-4">
                  <Info className="mt-0.5 size-4 shrink-0 text-info" aria-hidden />
                  <div>
                    <p className="text-sm font-medium text-ink">Before taking a plan loan</p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-muted">
                      A loan removes money from the market while it is outstanding, and it is repaid with after-tax
                      dollars. If your employment ends before the balance is repaid, the outstanding amount can be
                      treated as a taxable distribution.
                    </p>
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="Your loans" description={portal.plan.loans_allowed ? "Loans are permitted in this plan." : "Loans are not permitted in this plan."} />
                {loans.length === 0 ? (
                  <EmptyState
                    icon={Landmark}
                    title="No outstanding loans"
                    description="You have no plan loan on record, so your full balance stays invested."
                  />
                ) : (
                  <>
                    <Table>
                      <THead>
                        <TR>
                          <TH>Type</TH>
                          <TH align="right">Original</TH>
                          <TH align="right">Outstanding</TH>
                          <TH align="right">Rate</TH>
                          <TH align="right">Payment</TH>
                          <TH>Issued</TH>
                          <TH>Matures</TH>
                          <TH align="right">Status</TH>
                        </TR>
                      </THead>
                      <tbody>
                        {loans.map((loan) => (
                          <TR key={loan.id}>
                            <TD>
                              <Badge tone={loan.loan_type === "hardship" ? "warning" : "outline"} size="sm">
                                {titleCase(loan.loan_type)}
                              </Badge>
                            </TD>
                            <TD align="right" numeric>{formatCurrency(loan.original_amount)}</TD>
                            <TD align="right" numeric className="font-medium">{formatCurrency(loan.outstanding_balance)}</TD>
                            <TD align="right" numeric>{formatPercent(loan.interest_rate, { decimals: 2 })}</TD>
                            <TD align="right" numeric>{formatCurrency(loan.payment_amount)}</TD>
                            <TD className="whitespace-nowrap text-xs">{formatDate(loan.issued_on)}</TD>
                            <TD className="whitespace-nowrap text-xs">{formatDate(loan.matures_on)}</TD>
                            <TD align="right"><StatusBadge status={loan.status} /></TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                    <CardBody className="space-y-3">
                      {loans.map((loan) => {
                        const repaid = 1 - loan.outstanding_balance / loan.original_amount;
                        return (
                          <div key={loan.id}>
                            <div className="flex items-baseline justify-between text-xs">
                              <span className="text-ink-muted">
                                {titleCase(loan.loan_type)} loan · {loan.term_months}-month term
                              </span>
                              <span className="tabular text-ink">{formatPercent(repaid, { decimals: 0 })} repaid</span>
                            </div>
                            <Progress value={repaid} tone="primary" className="mt-1" />
                          </div>
                        );
                      })}
                    </CardBody>
                  </>
                )}
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
