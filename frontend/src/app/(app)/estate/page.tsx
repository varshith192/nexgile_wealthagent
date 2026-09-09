"use client";

/** Estate & trust (§16). Beneficiary changes route through approval. */

import { useState } from "react";
import { AlertTriangle, FileSignature, Scale, ShieldCheck, Users } from "lucide-react";

import { formatCurrency, formatDate, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Card, CardBody, CardHeader, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { CalcDisclosure, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type EstatePayload = {
  as_of: string;
  household: { id: string; name: string };
  projection: Calculation<{
    gross_estate: number;
    net_estate: number;
    estate_tax_payable: number;
    smooth_transfer_value: number;
    requires_succession_process: number;
    succession_readiness: number;
    findings: { severity: string; finding: string; detail: string }[];
    finding_count: number;
    note: string;
  }>;
  documents: {
    id: string;
    plan_name: string;
    document_type: string;
    status: string;
    executed_on: string | null;
    last_reviewed_on: string | null;
    next_review_due: string | null;
    attorney: string | null;
    jurisdiction: string | null;
    executor: string | null;
    notes: string | null;
    years_since_review: number | null;
    review_overdue: boolean;
  }[];
  trusts: {
    id: string;
    name: string;
    trust_type: string;
    grantor: string;
    trustee: string;
    successor_trustee: string | null;
    funded_amount: number;
    is_funded: boolean;
    established_on: string | null;
    situs: string | null;
    distribution_standard: string | null;
    status: string;
  }[];
  powers_of_attorney: {
    id: string;
    poa_type: string;
    principal: string;
    agent: string;
    successor_agent: string | null;
    executed_on: string | null;
    status: string;
  }[];
  beneficiaries: {
    id: string;
    account_name: string;
    account_type: string;
    full_name: string;
    relationship_type: string;
    designation: string;
    percentage: number;
    pending_percentage: number | null;
    is_charity: boolean;
    status: string;
    last_confirmed_on: string | null;
  }[];
  beneficiary_gaps: { account_id: string; account_name: string; account_type: string; balance: number; reason: string; current_total: number }[];
  family_tree: {
    household: string;
    principals: { id: string; name: string; birth_date: string | null }[];
    members: { id: string; name: string; relationship: string; birth_date: string | null; is_dependent: boolean }[];
  };
  distributions: {
    id: string;
    requested_by: string;
    beneficiary_name: string;
    amount: number;
    purpose: string;
    distribution_type: string;
    requested_on: string;
    status: string;
  }[];
  gifts: {
    usage: Calculation<{
      gifts: { recipient: string; amount: number; gifted_on: string; is_relative: boolean; exempt: boolean; basis: string }[];
      total_from_relatives: number;
      total_from_non_relatives: number;
      threshold: number;
      taxable_amount: number;
      threshold_breached: boolean;
      headroom: number;
    }>;
    gifts: { id: string; recipient: string; gift_type: string; amount: number; gifted_on: string; tax_year: number; is_relative: boolean; notes: string | null }[];
  };
  last_reviewed_on: string | null;
  review_reminders: { id: string; title: string; due: string; status: string }[];
};

export default function EstatePage() {
  const { data, error, loading, refetch } = useApi<EstatePayload>("/api/estate");
  const [tab, setTab] = useState("documents");

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(estate) => {
          const projection = estate.projection.result;

          return (
            <>
              <PageHeader
                title="Estate & Succession"
                description="Wills, trusts, powers of attorney and nominations. India levies no estate or inheritance tax — the objective is clarity and control, not tax."
                meta={
                  <>
                    <span className="text-xs text-ink-muted">As of {formatDate(estate.as_of)}</span>
                    {estate.last_reviewed_on ? (
                      <Badge tone={estate.documents.some((doc) => doc.review_overdue) ? "warning" : "positive"}>
                        Last reviewed {formatDate(estate.last_reviewed_on)}
                      </Badge>
                    ) : null}
                  </>
                }
              />

              <StatRow columns={4}>
                <StatTile label="Gross estate" value={formatCurrency(projection.gross_estate, { compact: true })} icon={Scale} tone="primary" />
                <StatTile
                  label="Transfers smoothly"
                  value={formatCurrency(projection.smooth_transfer_value, { compact: true })}
                  hint="Via nomination, joint holding or trust"
                />
                <StatTile
                  label="Needs a succession process"
                  value={formatCurrency(projection.requires_succession_process, { compact: true })}
                  hint="No nomination, joint holder or trust on file"
                  tone={projection.requires_succession_process > 0 ? "warning" : "positive"}
                />
                <StatTile
                  label="Succession readiness"
                  value={formatPercent(projection.succession_readiness, { decimals: 0 })}
                  icon={Users}
                />
              </StatRow>

              {estate.beneficiary_gaps.length > 0 ? (
                <Card className="border-negative/25 bg-negative-soft/40">
                  <CardBody className="flex flex-wrap gap-4 py-4">
                    <AlertTriangle className="mt-0.5 size-5 shrink-0 text-negative" aria-hidden />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-ink">
                        {estate.beneficiary_gaps.length} account
                        {estate.beneficiary_gaps.length === 1 ? "" : "s"} need a nomination
                      </p>
                      <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                        Without a nomination the family will need a succession certificate before the account can be
                        claimed. A nominee holds the asset as trustee for the legal heirs — it is not a substitute
                        for a will.
                      </p>
                      <ul className="mt-3 space-y-1.5">
                        {estate.beneficiary_gaps.map((gap) => (
                          <li key={gap.account_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-surface px-3 py-2 text-xs">
                            <span className="font-medium text-ink">{gap.account_name}</span>
                            <span className="text-ink-muted">{gap.reason}</span>
                            <span className="tabular font-medium text-ink">{formatCurrency(gap.balance, { compact: true })}</span>
                          </li>
                        ))}
                      </ul>
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
                      { value: "documents", label: "Documents", count: estate.documents.length + estate.powers_of_attorney.length },
                      { value: "trusts", label: "Trusts", count: estate.trusts.length },
                      { value: "beneficiaries", label: "Beneficiaries", count: estate.beneficiaries.length },
                      { value: "family", label: "Family" },
                      { value: "gifts", label: "Gifting", count: estate.gifts.gifts.length },
                      { value: "distributions", label: "Distributions", count: estate.distributions.length },
                    ]}
                  />
                </div>

                <CardBody className="space-y-5">
                  {tab === "documents" ? (
                    <>
                      <div className="space-y-3">
                        {estate.documents.map((document) => (
                          <div key={document.id} className={cn("rounded-lg border p-4", document.review_overdue ? "border-warning/30 bg-warning-soft/30" : "border-border")}>
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                                  <FileSignature className="size-4 text-ink-subtle" aria-hidden />
                                  {document.plan_name}
                                  <Badge tone="outline" size="sm">{titleCase(document.document_type)}</Badge>
                                  <StatusBadge status={document.status} />
                                </p>
                                {document.notes ? <p className="mt-1.5 text-xs leading-5 text-ink-muted">{document.notes}</p> : null}
                              </div>
                              {document.review_overdue ? <Badge tone="warning">Review overdue</Badge> : null}
                            </div>
                            <KeyValue
                              className="mt-3.5"
                              columns={3}
                              items={[
                                { label: "Executed", value: document.executed_on ? formatDate(document.executed_on) : "—" },
                                { label: "Last reviewed", value: document.last_reviewed_on ? formatDate(document.last_reviewed_on) : "—" },
                                { label: "Next review due", value: document.next_review_due ? formatDate(document.next_review_due) : "—" },
                                { label: "Attorney", value: document.attorney ?? "—" },
                                { label: "Jurisdiction", value: document.jurisdiction ?? "—" },
                                { label: "Executor", value: document.executor ?? "—" },
                              ]}
                            />
                          </div>
                        ))}
                      </div>

                      <div>
                        <p className="section-label">Powers of attorney</p>
                        <div className="mt-2.5 scroll-x rounded-md border border-border">
                          <Table>
                            <THead>
                              <TR>
                                <TH>Type</TH>
                                <TH>Principal</TH>
                                <TH>Agent</TH>
                                <TH>Successor</TH>
                                <TH>Executed</TH>
                                <TH align="right">Status</TH>
                              </TR>
                            </THead>
                            <tbody>
                              {estate.powers_of_attorney.map((poa) => (
                                <TR key={poa.id}>
                                  <TD className="font-medium">{titleCase(poa.poa_type)}</TD>
                                  <TD className="text-xs">{poa.principal}</TD>
                                  <TD className="text-xs">{poa.agent}</TD>
                                  <TD className="text-xs text-ink-muted">{poa.successor_agent ?? "—"}</TD>
                                  <TD className="text-xs">{poa.executed_on ? formatDate(poa.executed_on) : "—"}</TD>
                                  <TD align="right"><StatusBadge status={poa.status} /></TD>
                                </TR>
                              ))}
                            </tbody>
                          </Table>
                        </div>
                      </div>
                    </>
                  ) : null}

                  {tab === "trusts" ? (
                    estate.trusts.length === 0 ? (
                      <EmptyState title="No trusts on file" description="This household holds no trust structures in the platform." />
                    ) : (
                      <div className="grid gap-4 lg:grid-cols-2">
                        {estate.trusts.map((trust) => (
                          <div key={trust.id} className="rounded-lg border border-border p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-ink">{trust.name}</p>
                                <p className="mt-1 flex flex-wrap gap-1.5">
                                  <Badge tone="outline" size="sm">{titleCase(trust.trust_type)}</Badge>
                                  <StatusBadge status={trust.status} />
                                  {trust.is_funded ? <Badge tone="positive" size="sm">Funded</Badge> : <Badge tone="warning" size="sm">Unfunded</Badge>}
                                </p>
                              </div>
                              <p className="shrink-0 text-right text-lg font-semibold tabular text-ink">
                                {formatCurrency(trust.funded_amount, { compact: true })}
                              </p>
                            </div>
                            <KeyValue
                              className="mt-3.5"
                              columns={1}
                              items={[
                                { label: "Grantor", value: trust.grantor },
                                { label: "Trustee", value: trust.trustee },
                                { label: "Successor trustee", value: trust.successor_trustee ?? "—" },
                                { label: "Situs", value: trust.situs ?? "—" },
                                { label: "Established", value: trust.established_on ? formatDate(trust.established_on) : "—" },
                                { label: "Distribution standard", value: trust.distribution_standard ?? "—" },
                              ]}
                            />
                          </div>
                        ))}
                      </div>
                    )
                  ) : null}

                  {tab === "beneficiaries" ? (
                    <>
                      <p className="text-sm text-ink-muted">
                        A beneficiary designation overrides your will for that account. Changes move through
                        draft → review → approval → completed.
                      </p>
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Account</TH>
                              <TH>Beneficiary</TH>
                              <TH>Relationship</TH>
                              <TH>Designation</TH>
                              <TH align="right">Share</TH>
                              <TH>Last confirmed</TH>
                              <TH align="right">Status</TH>
                            </TR>
                          </THead>
                          <tbody>
                            {estate.beneficiaries.map((beneficiary) => (
                              <TR key={beneficiary.id}>
                                <TD className="text-xs">{beneficiary.account_name}</TD>
                                <TD className="font-medium">
                                  {beneficiary.full_name}
                                  {beneficiary.is_charity ? <Badge tone="outline" size="sm" className="ml-1.5">Charity</Badge> : null}
                                </TD>
                                <TD className="text-xs">{titleCase(beneficiary.relationship_type)}</TD>
                                <TD>
                                  <Badge tone={beneficiary.designation === "primary" ? "primary" : "outline"} size="sm">
                                    {titleCase(beneficiary.designation)}
                                  </Badge>
                                </TD>
                                <TD align="right" numeric className="font-medium">
                                  {formatPercent(beneficiary.percentage / 100, { decimals: 0 })}
                                  {beneficiary.pending_percentage !== null ? (
                                    <span className="ml-1.5 text-2xs text-warning">
                                      → {formatPercent(beneficiary.pending_percentage / 100, { decimals: 0 })}
                                    </span>
                                  ) : null}
                                </TD>
                                <TD className="text-xs text-ink-muted">
                                  {beneficiary.last_confirmed_on ? formatDate(beneficiary.last_confirmed_on) : "—"}
                                </TD>
                                <TD align="right"><StatusBadge status={beneficiary.status} /></TD>
                              </TR>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                    </>
                  ) : null}

                  {tab === "family" ? (
                    <div className="grid gap-4 lg:grid-cols-2">
                      <div>
                        <p className="section-label">Principals</p>
                        <ul className="mt-2.5 space-y-2">
                          {estate.family_tree.principals.map((person) => (
                            <li key={person.id} className="flex items-center justify-between gap-3 rounded-md border border-border px-3.5 py-2.5">
                              <span className="text-sm font-medium text-ink">{person.name}</span>
                              <span className="text-xs text-ink-muted">
                                {person.birth_date ? `Born ${formatDate(person.birth_date)}` : "—"}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="section-label">Family members</p>
                        <ul className="mt-2.5 space-y-2">
                          {estate.family_tree.members.map((member) => (
                            <li key={member.id} className="flex items-center justify-between gap-3 rounded-md border border-border px-3.5 py-2.5">
                              <span className="min-w-0">
                                <span className="block truncate text-sm font-medium text-ink">{member.name}</span>
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
                    </div>
                  ) : null}

                  {tab === "gifts" ? (
                    <>
                      <p className="text-sm text-ink-muted">
                        Section 56(2)(x): gifts between specified relatives are exempt regardless of amount. Gifts
                        from a non-relative are taxable in full — not just the excess — once they cross{" "}
                        {formatCurrency(estate.gifts.usage.result.threshold)} in a financial year.
                      </p>
                      <KeyValue
                        columns={3}
                        items={[
                          { label: "From relatives (exempt)", value: formatCurrency(estate.gifts.usage.result.total_from_relatives) },
                          { label: "From non-relatives", value: formatCurrency(estate.gifts.usage.result.total_from_non_relatives) },
                          {
                            label: "Taxable amount",
                            value: formatCurrency(estate.gifts.usage.result.taxable_amount),
                            hint: estate.gifts.usage.result.threshold_breached ? "Threshold breached — the full amount is taxable" : undefined,
                          },
                        ]}
                      />

                      <div>
                        <p className="section-label">Gift history</p>
                        <ul className="mt-2.5 divide-y divide-border rounded-md border border-border">
                          {estate.gifts.gifts.map((gift) => (
                            <li key={gift.id} className="flex items-center justify-between gap-3 px-3.5 py-2.5">
                              <span className="min-w-0">
                                <span className="flex items-center gap-2 text-sm font-medium text-ink">
                                  {gift.recipient}
                                  <Badge tone="outline" size="sm">{titleCase(gift.gift_type)}</Badge>
                                  <Badge tone={gift.is_relative ? "positive" : "warning"} size="sm">
                                    {gift.is_relative ? "Specified relative" : "Non-relative"}
                                  </Badge>
                                </span>
                                <span className="mt-0.5 block text-xs text-ink-muted">
                                  {formatDate(gift.gifted_on)} · FY {gift.tax_year}-{String(gift.tax_year + 1).slice(-2)}
                                </span>
                              </span>
                              <span className="shrink-0 text-sm font-medium tabular text-ink">{formatCurrency(gift.amount)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      <CalcDisclosure calculation={estate.gifts.usage} label="How the gift tax position is calculated" />
                    </>
                  ) : null}

                  {tab === "distributions" ? (
                    estate.distributions.length === 0 ? (
                      <EmptyState title="No distribution requests" description="Trust distribution requests appear here for review and approval." />
                    ) : (
                      <div className="scroll-x rounded-md border border-border">
                        <Table>
                          <THead>
                            <TR>
                              <TH>Requested</TH>
                              <TH>Beneficiary</TH>
                              <TH>Purpose</TH>
                              <TH>Type</TH>
                              <TH align="right">Amount</TH>
                              <TH align="right">Status</TH>
                            </TR>
                          </THead>
                          <tbody>
                            {estate.distributions.map((distribution) => (
                              <TR key={distribution.id}>
                                <TD className="text-xs">
                                  {formatDate(distribution.requested_on)}
                                  <span className="mt-0.5 block text-2xs text-ink-subtle">by {distribution.requested_by}</span>
                                </TD>
                                <TD className="font-medium">{distribution.beneficiary_name}</TD>
                                <TD className="max-w-[18rem] text-xs text-ink-muted">{distribution.purpose}</TD>
                                <TD><Badge tone="outline" size="sm">{titleCase(distribution.distribution_type)}</Badge></TD>
                                <TD align="right" numeric className="font-medium">{formatCurrency(distribution.amount)}</TD>
                                <TD align="right"><StatusBadge status={distribution.status} /></TD>
                              </TR>
                            ))}
                          </tbody>
                        </Table>
                      </div>
                    )
                  ) : null}
                </CardBody>
              </Card>

              <Card>
                <CardHeader title="Succession readiness" description="A planning view, not legal advice. Confirm every figure with your estate lawyer." />
                <CardBody className="space-y-4">
                  <KeyValue
                    columns={3}
                    items={[
                      { label: "Gross estate", value: formatCurrency(projection.gross_estate, { compact: true }) },
                      { label: "Net estate", value: formatCurrency(projection.net_estate, { compact: true }) },
                      { label: "Transfers smoothly", value: formatCurrency(projection.smooth_transfer_value, { compact: true }) },
                      { label: "Needs succession process", value: formatCurrency(projection.requires_succession_process, { compact: true }) },
                      { label: "Succession readiness", value: formatPercent(projection.succession_readiness, { decimals: 0 }) },
                      { label: "Estate or inheritance tax", value: formatCurrency(projection.estate_tax_payable) },
                    ]}
                  />
                  {projection.findings.length > 0 ? (
                    <ul className="space-y-2">
                      {projection.findings.map((finding) => (
                        <li key={finding.finding} className="rounded-md border border-border px-3.5 py-2.5">
                          <p className="flex items-center gap-2 text-sm font-medium text-ink">
                            <Badge tone={finding.severity === "high" ? "warning" : "outline"} size="sm">{titleCase(finding.severity)}</Badge>
                            {finding.finding}
                          </p>
                          <p className="mt-1 text-xs leading-5 text-ink-muted">{finding.detail}</p>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  <CalcDisclosure calculation={estate.projection} />
                  <p className="flex items-start gap-2 text-xs leading-relaxed text-ink-subtle">
                    <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                    {projection.note}
                  </p>
                </CardBody>
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
