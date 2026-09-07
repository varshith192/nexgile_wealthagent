"use client";

/**
 * Rebalancing (§23).
 *
 * Current allocation → target → proposed changes → trade preview → review →
 * approval → simulated execution. Nexgile never routes an order to a broker.
 */

import { useState } from "react";
import Link from "next/link";
import { Activity, ArrowRight, Play, ShieldAlert } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatDateTime, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { Calculation } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Drawer, Select, TD, TH, THead, TR, Table } from "@/components/ui";
import { DivergingBars } from "@/components/charts";
import { CalcDisclosure, StatusBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type RebalanceSummary = {
  id: string;
  name: string;
  household_id: string;
  household: string;
  status: string;
  max_drift: number;
  turnover_amount: number;
  estimated_tax_cost: number;
  estimated_trading_cost: number;
  trade_count: number;
  approval_id: string | null;
  is_simulated: boolean;
  created_at: string;
  executed_at: string | null;
};

type RebalanceDetail = RebalanceSummary & {
  strategy_note: string | null;
  trades: {
    id: string;
    account_name: string;
    symbol: string;
    name: string;
    asset_class: string | null;
    side: string;
    quantity: number;
    estimated_price: number;
    estimated_amount: number;
    realized_gain: number;
    tax_impact: number;
    rationale: string | null;
    status: string;
  }[];
  current_allocation: Calculation<{ total: number; rows: { key: string; label: string; market_value: number; weight: number }[] }>;
  target_allocation: { asset_class: string; asset_class_label: string; target_weight: number; tolerance_band: number }[];
  drift: Calculation<{ rows: { asset_class: string; label: string; current_weight: number; target_weight: number; drift: number; tolerance_band: number; breached: boolean; dollar_drift: number }[]; max_drift: number; breach_count: number }>;
  calculation: Calculation<Record<string, unknown>> | null;
  execution_note: string;
};

type ClientOption = { household_id: string; name: string };

export default function RebalancingPage() {
  const { data, error, loading, refetch } = useApi<RebalanceSummary[]>("/api/advisor/rebalancing");
  const { data: clients } = useApi<{ clients: ClientOption[] }>("/api/advisor/clients");
  const [householdId, setHouseholdId] = useState("");
  const [detail, setDetail] = useState<RebalanceDetail | null>(null);

  const { run: propose, pending, message } = useMutation(async () => {
    const created = await api.post<RebalanceDetail>("/api/advisor/rebalancing", {
      household_id: householdId || clients?.clients[0]?.household_id,
    });
    setDetail(created);
    refetch();
    return created;
  });

  const { run: open } = useMutation(async (id: string) => {
    const payload = await api.get<RebalanceDetail>(`/api/advisor/rebalancing/${id}`);
    setDetail(payload);
    return payload;
  });

  const { run: execute, pending: executing } = useMutation(async (id: string) => {
    const payload = await api.post<RebalanceDetail>(`/api/advisor/rebalancing/${id}/execute`);
    setDetail(payload);
    refetch();
    return payload;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Rebalancing"
        description="Turn allocation drift into a reviewable trade set. Approved proposals are executed in simulation only."
        actions={
          <div className="flex items-center gap-2">
            <Select
              value={householdId}
              onChange={(event) => setHouseholdId(event.target.value)}
              className="h-9 w-56 text-xs"
              aria-label="Choose a household"
            >
              <option value="">Select a household…</option>
              {clients?.clients.map((client) => (
                <option key={client.household_id} value={client.household_id}>
                  {client.name}
                </option>
              ))}
            </Select>
            <Button variant="primary" size="sm" loading={pending} onClick={() => propose()}>
              <Play />
              Model a rebalance
            </Button>
          </div>
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
            <p className="text-sm font-medium text-ink">Draft → Pending review → Approved → Submitted → Completed</p>
            <p className="mt-1 text-xs leading-relaxed text-ink-muted">
              Nexgile WealthAgent does not connect to a brokerage. A proposal is a trade list for discussion; once
              approved it is marked executed in simulation and written to the audit trail as such.
            </p>
          </div>
        </CardBody>
      </Card>

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Proposals" value={String(data.length)} icon={Activity} tone="primary" />
          <StatTile
            label="Awaiting review"
            value={String(data.filter((row) => row.status === "pending_review").length)}
            tone={data.some((row) => row.status === "pending_review") ? "warning" : "positive"}
          />
          <StatTile
            label="Total turnover proposed"
            value={formatCurrency(data.reduce((total, row) => total + row.turnover_amount, 0), { compact: true })}
          />
          <StatTile
            label="Estimated tax cost"
            value={formatCurrency(data.reduce((total, row) => total + row.estimated_tax_cost, 0), { compact: true })}
          />
        </StatRow>
      ) : null}

      <Card>
        <CardHeader title="Proposals" description="Every rebalance raised across your book." />
        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={5} />}
          emptyWhen={(rows) => rows.length === 0}
          empty={
            <EmptyState
              icon={Activity}
              title="No rebalance proposals"
              description="Pick a household and model one to see the proposed trades."
            />
          }
        >
          {(rows) => (
            <Table>
              <THead>
                <TR>
                  <TH>Proposal</TH>
                  <TH>Household</TH>
                  <TH align="right">Max drift</TH>
                  <TH align="right">Trades</TH>
                  <TH align="right">Turnover</TH>
                  <TH align="right">Tax cost</TH>
                  <TH align="right">Status</TH>
                </TR>
              </THead>
              <tbody>
                {rows.map((row) => (
                  <TR key={row.id} className="cursor-pointer" onClick={() => open(row.id)}>
                    <TD>
                      <span className="font-medium">{row.name}</span>
                      <span className="mt-0.5 block text-xs text-ink-muted">
                        Created {formatDate(row.created_at)}
                        {row.executed_at ? ` · executed ${formatDate(row.executed_at)}` : ""}
                      </span>
                    </TD>
                    <TD className="text-xs">{row.household}</TD>
                    <TD align="right" numeric>{formatPercent(row.max_drift, { decimals: 1 })}</TD>
                    <TD align="right" numeric>{row.trade_count}</TD>
                    <TD align="right" numeric>{formatCurrency(row.turnover_amount, { compact: true })}</TD>
                    <TD align="right" numeric className={row.estimated_tax_cost > 0 ? "text-warning" : "text-ink-subtle"}>
                      {formatCurrency(row.estimated_tax_cost, { compact: true })}
                    </TD>
                    <TD align="right">
                      <span className="flex items-center justify-end gap-1.5">
                        <StatusBadge status={row.status} />
                        {row.is_simulated ? <Badge tone="outline" size="sm">Simulated</Badge> : null}
                      </span>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataState>
      </Card>

      <RebalanceDrawer
        detail={detail}
        onClose={() => setDetail(null)}
        onExecute={execute}
        executing={executing}
      />
    </div>
  );
}

function RebalanceDrawer({
  detail,
  onClose,
  onExecute,
  executing,
}: {
  detail: RebalanceDetail | null;
  onClose: () => void;
  onExecute: (id: string) => void;
  executing: boolean;
}) {
  if (!detail) return <Drawer open={false} onClose={onClose} title="Rebalance">{null}</Drawer>;

  const buys = detail.trades.filter((trade) => trade.side === "buy");
  const sells = detail.trades.filter((trade) => trade.side === "sell");

  return (
    <Drawer
      open
      onClose={onClose}
      title={detail.name}
      description={`${detail.household} · ${detail.trade_count} proposed trades`}
      width="max-w-3xl"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-ink-muted">{detail.execution_note}</p>
          <div className="flex gap-2">
            {detail.approval_id ? (
              <Link href="/approvals">
                <Button size="sm">
                  Open in approvals
                  <ArrowRight />
                </Button>
              </Link>
            ) : null}
            {detail.status === "approved" ? (
              <Button size="sm" variant="primary" loading={executing} onClick={() => onExecute(detail.id)}>
                Execute (simulated)
              </Button>
            ) : null}
          </div>
        </div>
      }
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={detail.status} />
          {detail.is_simulated ? <Badge tone="outline">Simulated execution only</Badge> : null}
        </div>

        {detail.strategy_note ? <p className="text-sm leading-6 text-ink-muted">{detail.strategy_note}</p> : null}

        <KeyValue
          columns={2}
          items={[
            { label: "Maximum drift", value: formatPercent(detail.max_drift, { decimals: 1 }) },
            { label: "Turnover", value: formatCurrency(detail.turnover_amount) },
            { label: "Estimated tax cost", value: formatCurrency(detail.estimated_tax_cost) },
            { label: "Estimated trading cost", value: formatCurrency(detail.estimated_trading_cost) },
            { label: "Buys", value: String(buys.length) },
            { label: "Sells", value: String(sells.length) },
          ]}
        />

        <section>
          <h3 className="section-label">Current allocation against policy</h3>
          <div className="mt-2.5">
            <DivergingBars
              data={detail.drift.result.rows.map((row) => ({ label: row.label, value: row.drift, band: row.tolerance_band }))}
              height={Math.max(180, detail.drift.result.rows.length * 32)}
            />
          </div>
          <div className="mt-3 scroll-x rounded-md border border-border">
            <Table>
              <THead>
                <TR>
                  <TH>Asset class</TH>
                  <TH align="right">Current</TH>
                  <TH align="right">Target</TH>
                  <TH align="right">Drift</TH>
                  <TH align="right">Dollar gap</TH>
                </TR>
              </THead>
              <tbody>
                {detail.drift.result.rows.map((row) => (
                  <TR key={row.asset_class}>
                    <TD className="font-medium">{row.label}</TD>
                    <TD align="right" numeric>{formatPercent(row.current_weight, { decimals: 1 })}</TD>
                    <TD align="right" numeric className="text-ink-muted">{formatPercent(row.target_weight, { decimals: 1 })}</TD>
                    <TD align="right" numeric className={row.breached ? "font-medium text-warning" : ""}>
                      {formatPercent(row.drift, { decimals: 1, signed: true })}
                    </TD>
                    <TD align="right" numeric>{formatCurrency(row.dollar_drift, { compact: true, signed: true })}</TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          </div>
        </section>

        <section>
          <h3 className="section-label">Trade preview</h3>
          {detail.trades.length === 0 ? (
            <p className="mt-2 text-sm text-ink-muted">
              No trade clears the minimum size. The portfolio is close enough to policy that trading would cost more
              than it corrects.
            </p>
          ) : (
            <div className="mt-2.5 scroll-x rounded-md border border-border">
              <Table>
                <THead>
                  <TR>
                    <TH>Side</TH>
                    <TH>Security</TH>
                    <TH>Account</TH>
                    <TH align="right">Quantity</TH>
                    <TH align="right">Price</TH>
                    <TH align="right">Amount</TH>
                    <TH align="right">Tax impact</TH>
                    <TH align="right">Status</TH>
                  </TR>
                </THead>
                <tbody>
                  {detail.trades.map((trade) => (
                    <TR key={trade.id}>
                      <TD>
                        <Badge tone={trade.side === "sell" ? "warning" : "positive"} size="sm">
                          {trade.side.toUpperCase()}
                        </Badge>
                      </TD>
                      <TD>
                        <span className="font-medium">{trade.symbol}</span>
                        <span className="mt-0.5 block max-w-[14rem] truncate text-xs text-ink-muted">{trade.name}</span>
                        {trade.rationale ? (
                          <span className="mt-0.5 block max-w-[16rem] text-2xs text-ink-subtle">{trade.rationale}</span>
                        ) : null}
                      </TD>
                      <TD className="text-xs text-ink-muted">{trade.account_name}</TD>
                      <TD align="right" numeric>{formatNumber(trade.quantity, 2)}</TD>
                      <TD align="right" numeric>{formatCurrency(trade.estimated_price, { decimals: 2 })}</TD>
                      <TD align="right" numeric className="font-medium">{formatCurrency(trade.estimated_amount)}</TD>
                      <TD align="right" numeric className={trade.tax_impact > 0 ? "text-warning" : "text-ink-subtle"}>
                        {trade.tax_impact > 0 ? formatCurrency(trade.tax_impact) : "—"}
                      </TD>
                      <TD align="right"><StatusBadge status={trade.status} /></TD>
                    </TR>
                  ))}
                </tbody>
              </Table>
            </div>
          )}
        </section>

        {detail.calculation ? <CalcDisclosure calculation={detail.calculation} label="How this plan was built" /> : null}
      </div>
    </Drawer>
  );
}
