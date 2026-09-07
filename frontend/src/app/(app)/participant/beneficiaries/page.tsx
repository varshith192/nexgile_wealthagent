"use client";

/** Participant beneficiary designation status. */

import { CircleCheck, Scale, TriangleAlert } from "lucide-react";

import { formatCurrency, formatDate } from "@/lib/format";
import type { ParticipantPortal } from "@/lib/participant";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardBody, CardHeader } from "@/components/ui";
import { KeyValue, PageHeader } from "@/components/shared/page";
import { DataState, LoadingGrid } from "@/components/shared/states";

export default function ParticipantBeneficiariesPage() {
  const { data, error, loading, refetch } = useApi<ParticipantPortal>("/api/participant");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Beneficiaries"
        description="Who inherits this account. Your designation here overrides your will for this balance."
      />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={2} columns={2} />}>
        {(portal) => {
          const hasBeneficiary = portal.participant.has_beneficiary;

          return (
            <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
              <Card className={hasBeneficiary ? "border-positive/25 bg-positive-soft/30" : "border-warning/25 bg-warning-soft/40"}>
                <CardBody className="py-6">
                  <div className="flex items-start gap-4">
                    <span
                      className={`flex size-11 shrink-0 items-center justify-center rounded-full ${
                        hasBeneficiary ? "bg-positive/15" : "bg-warning/15"
                      }`}
                    >
                      {hasBeneficiary ? (
                        <CircleCheck className="size-5 text-positive" aria-hidden />
                      ) : (
                        <TriangleAlert className="size-5 text-warning" aria-hidden />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="text-base font-semibold text-ink">
                        {hasBeneficiary ? "A beneficiary is on file" : "No beneficiary on file"}
                      </p>
                      <p className="mt-1.5 text-sm leading-6 text-ink-muted">
                        {hasBeneficiary
                          ? "Your designation is recorded with the plan recordkeeper. Review it after any marriage, divorce, birth or death in the family."
                          : "Without a valid designation, this balance passes according to the plan document and may go through probate rather than directly to the person you intend."}
                      </p>
                      <p className="mt-3 text-xs leading-relaxed text-ink-subtle">{portal.beneficiaries.note}</p>
                      <p className="mt-4 rounded-md bg-surface px-3.5 py-2.5 text-xs leading-relaxed text-ink-muted">
                        Beneficiary designations for this plan are held by{" "}
                        <span className="font-medium text-ink">{portal.plan.recordkeeper}</span>. Changes made here
                        route through your plan sponsor for confirmation before they take effect.
                      </p>
                    </div>
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="Account covered" description="The balance this designation applies to." />
                <CardBody>
                  <KeyValue
                    columns={1}
                    items={[
                      { label: "Plan", value: portal.plan.name },
                      { label: "Sponsor", value: portal.plan.sponsor },
                      { label: "Account balance", value: formatCurrency(portal.participant.account_balance) },
                      { label: "Vested balance", value: formatCurrency(portal.participant.vested_balance) },
                      { label: "Roth balance", value: formatCurrency(portal.participant.roth_balance) },
                      { label: "Recordkeeper", value: portal.plan.recordkeeper },
                      { label: "As of", value: formatDate(portal.as_of) },
                    ]}
                  />
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    <Badge tone={hasBeneficiary ? "positive" : "warning"}>
                      <Scale className="size-3" />
                      {hasBeneficiary ? "Designation complete" : "Designation missing"}
                    </Badge>
                  </div>
                </CardBody>
              </Card>
            </div>
          );
        }}
      </DataState>
    </div>
  );
}
