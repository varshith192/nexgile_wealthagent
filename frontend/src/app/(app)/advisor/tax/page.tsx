"use client";

/**
 * Advisor tax planning (§24).
 *
 * Identify → Analyse → Review → Approve → Simulated action. Raising a harvest
 * proposal creates an approval record; nothing trades.
 */

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Receipt, ShieldAlert, TrendingDown } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { Badge, Button, Card, CardBody, CardHeader, Select, TD, TH, THead, TR, Table } from "@/components/ui";
import { CalcDisclosure, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, Section, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type HarvestCandidate = {
  lot_id: string;
  symbol: string;
  name: string;
  account_name: string;
  quantity: number;
  cost_basis: number;
  market_value: number;
  unrealized_loss: number;
  holding_period: string;
  acquired_on: string;
  estimated_tax_benefit: number;
  wash_sale_risk: string;
  replacement_symbol: string | null;
};

type TaxPayload = {
  tax_year: number;
  as_of: string;
  harvest: Calculation<{
    opportunities: HarvestCandidate[];
    opportunity_count: number;
    total_harvestable_loss: number;
    total_estimated_benefit: number;
  }>;
  realized_gains: Calculation<{ short_term_gain: number; long_term_gain: number; net_gain: number }>;
  capital_gains_budget: Calculation<{ budget: number; used: number; remaining: number; utilisation: number; over_budget: boolean }>;
};

type HarvestProposal = {
  id: string;
  symbol: string | null;
  security_name: string | null;
  account_name: string | null;
  quantity: number;
  unrealized_loss: number;
  estimated_tax_benefit: number;
  holding_period: string;
  wash_sale_risk: string;
  wash_sale_window_ends: string | null;
  replacement_symbol: string | null;
  status: string;
  approval_id: string | null;
  is_simulated: boolean;
  executed_at: string | null;
};

export default function AdvisorTaxPage() {
  const { data: clients } = useApi<{ clients: { household_id: string; name: string }[] }>("/api/advisor/clients");
  const [householdId, setHouseholdId] = useState("");
  const suffix = householdId ? `?household_id=${householdId}` : "";

  const { data, error, loading, refetch } = useApi<TaxPayload>(`/api/tax${suffix}`, [householdId]);
  const { data: harvests, refetch: refetchHarvests } = useApi<HarvestProposal[]>(`/api/tax/harvests${suffix}`, [householdId]);

  const proposed = new Set((harvests ?? []).map((row) => row.symbol));

  const { run: propose, pending, message } = useMutation(async (lotId: string) => {
    const created = await api.post("/api/tax/harvests", {
      tax_lot_id: lotId,
      household_id: householdId || undefined,
    });
    refetchHarvests();
    refetch();
    return created;
  });

  const { run: execute, pending: executing } = useMutation(async (harvestId: string) => {
    const result = await api.post(`/api/tax/harvests/${harvestId}/execute`);
    refetchHarvests();
    return result;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Tax planning"
        description="Harvesting candidates across the book, and the proposals raised from them."
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

      {message ? (
        <div role="alert" className="rounded-md border border-negative/25 bg-negative-soft px-4 py-3 text-sm text-negative">
          {message}
        </div>
      ) : null}

      <Card className="border-info/25 bg-info-soft/40">
        <CardBody className="flex flex-wrap items-start gap-3 py-4">
          <ShieldAlert className="mt-0.5 size-4 shrink-0 text-info" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-ink">Identify → Analyse → Review → Approve → Simulated action</p>
            <p className="mt-1 text-xs leading-relaxed text-ink-muted">
              Raising a proposal creates an approval record for the tax specialist. Execution is simulated and opens a
              31-day wash-sale window so the replacement is held long enough for the loss to count.
            </p>
          </div>
        </CardBody>
      </Card>

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={6} />}>
        {(tax) => {
          const harvest = tax.harvest.result;
          const budget = tax.capital_gains_budget.result;
          const realized = tax.realized_gains.result;

          return (
            <>
              <StatRow columns={4}>
                <StatTile
                  label="Harvest candidates"
                  value={String(harvest.opportunity_count)}
                  icon={TrendingDown}
                  tone={harvest.opportunity_count ? "primary" : "default"}
                />
                <StatTile
                  label="Harvestable loss"
                  value={formatCurrency(harvest.total_harvestable_loss, { compact: true })}
                  hint={`Tax year ${tax.tax_year}`}
                />
                <StatTile
                  label="Estimated tax benefit"
                  value={formatCurrency(harvest.total_estimated_benefit, { compact: true })}
                  tone="positive"
                  icon={Receipt}
                />
                <StatTile
                  label="Gain budget remaining"
                  value={formatCurrency(budget.remaining, { compact: true })}
                  hint={`Net realised ${formatCurrency(realized.net_gain, { compact: true })}`}
                  tone={budget.over_budget ? "negative" : "default"}
                />
              </StatRow>

              <Card>
                <CardHeader
                  title="Candidates"
                  description="Open lots holding a loss above the review threshold, with a replacement that preserves exposure."
                />
                {harvest.opportunities.length === 0 ? (
                  <EmptyState icon={TrendingDown} title="No harvesting candidates" description="No open lot currently holds a material loss." />
                ) : (
                  <Table>
                    <THead>
                      <TR>
                        <TH>Security</TH>
                        <TH>Account</TH>
                        <TH align="right">Quantity</TH>
                        <TH align="right">Cost basis</TH>
                        <TH align="right">Market value</TH>
                        <TH align="right">Loss</TH>
                        <TH>Period</TH>
                        <TH align="right">Benefit</TH>
                        <TH>Wash sale</TH>
                        <TH>Replacement</TH>
                        <TH align="right"> </TH>
                      </TR>
                    </THead>
                    <tbody>
                      {harvest.opportunities.map((row) => (
                        <TR key={row.lot_id}>
                          <TD>
                            <span className="font-medium">{row.symbol}</span>
                            <span className="mt-0.5 block max-w-[13rem] truncate text-xs text-ink-muted">{row.name}</span>
                            <span className="mt-0.5 block text-2xs text-ink-subtle">Acquired {formatDate(row.acquired_on)}</span>
                          </TD>
                          <TD className="text-xs text-ink-muted">{row.account_name}</TD>
                          <TD align="right" numeric>{formatNumber(row.quantity, 2)}</TD>
                          <TD align="right" numeric>{formatCurrency(row.cost_basis, { compact: true })}</TD>
                          <TD align="right" numeric>{formatCurrency(row.market_value, { compact: true })}</TD>
                          <TD align="right" numeric className="font-medium text-negative">
                            {formatCurrency(row.unrealized_loss, { compact: true })}
                          </TD>
                          <TD>
                            <Badge tone={row.holding_period === "long_term" ? "positive" : "neutral"} size="sm">
                              {row.holding_period === "long_term" ? "Long" : "Short"}
                            </Badge>
                          </TD>
                          <TD align="right" numeric className="font-medium text-positive">
                            {formatCurrency(row.estimated_tax_benefit)}
                          </TD>
                          <TD><StatusBadge status={row.wash_sale_risk} /></TD>
                          <TD className="text-xs">{row.replacement_symbol ?? "—"}</TD>
                          <TD align="right">
                            {proposed.has(row.symbol) ? (
                              <Badge tone="outline" size="sm">Proposed</Badge>
                            ) : (
                              <Button
                                size="sm"
                                variant="primary"
                                loading={pending}
                                disabled={row.wash_sale_risk === "blocked"}
                                onClick={() => propose(row.lot_id)}
                              >
                                Raise
                              </Button>
                            )}
                          </TD>
                        </TR>
                      ))}
                    </tbody>
                  </Table>
                )}
                <CardBody>
                  <CalcDisclosure calculation={tax.harvest} />
                </CardBody>
              </Card>

              <Section title="Harvest proposals" description="Raised proposals and their approval status.">
                <Card>
                  {!harvests || harvests.length === 0 ? (
                    <EmptyState title="No proposals raised" description="Raise one from the candidate list above." />
                  ) : (
                    <Table>
                      <THead>
                        <TR>
                          <TH>Security</TH>
                          <TH>Account</TH>
                          <TH align="right">Loss</TH>
                          <TH align="right">Benefit</TH>
                          <TH>Replacement</TH>
                          <TH>Wash-sale window</TH>
                          <TH align="right">Status</TH>
                          <TH align="right"> </TH>
                        </TR>
                      </THead>
                      <tbody>
                        {harvests.map((proposal) => (
                          <TR key={proposal.id}>
                            <TD>
                              <span className="font-medium">{proposal.symbol}</span>
                              <span className="mt-0.5 block max-w-[13rem] truncate text-xs text-ink-muted">
                                {proposal.security_name}
                              </span>
                            </TD>
                            <TD className="text-xs text-ink-muted">{proposal.account_name}</TD>
                            <TD align="right" numeric className="text-negative">{formatCurrency(proposal.unrealized_loss, { compact: true })}</TD>
                            <TD align="right" numeric className="font-medium text-positive">
                              {formatCurrency(proposal.estimated_tax_benefit)}
                            </TD>
                            <TD className="text-xs">{proposal.replacement_symbol ?? "—"}</TD>
                            <TD className="text-xs text-ink-muted">
                              {proposal.wash_sale_window_ends ? `until ${formatDate(proposal.wash_sale_window_ends)}` : "—"}
                            </TD>
                            <TD align="right">
                              <span className="flex items-center justify-end gap-1.5">
                                <StatusBadge status={proposal.status} />
                                {proposal.is_simulated ? <Badge tone="outline" size="sm">Simulated</Badge> : null}
                              </span>
                            </TD>
                            <TD align="right">
                              {proposal.status === "approved" ? (
                                <Button size="sm" variant="primary" loading={executing} onClick={() => execute(proposal.id)}>
                                  Execute
                                </Button>
                              ) : proposal.approval_id ? (
                                <Link href="/approvals">
                                  <Button size="sm" variant="ghost">
                                    Review <ArrowRight />
                                  </Button>
                                </Link>
                              ) : null}
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card>
              </Section>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
