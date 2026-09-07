"use client";

/** Account detail: balances, holdings and recent transactions. */

import { use } from "react";

import { formatCurrency, formatDate, formatNumber, formatPercent, titleCase } from "@/lib/format";
import type { AccountRow, Calculation } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Card, CardBody, CardHeader, TD, TH, THead, TR, Table } from "@/components/ui";
import { CalcDisclosure, Delta, FreshnessBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type AccountDetailPayload = {
  account: AccountRow;
  valuation: Calculation<{
    market_value: number;
    cost_basis: number;
    unrealized_gain: number;
    unrealized_gain_percent: number;
    day_change: number;
    day_change_percent: number;
    cash: number;
  }>;
  holdings: {
    holding_id: string;
    symbol: string;
    name: string;
    quantity: number;
    price: number;
    asset_class_label: string;
    market_value: number;
    cost_basis: number;
    gain_loss: number;
    gain_loss_percent: number;
  }[];
  transactions: {
    id: string;
    trade_date: string;
    type: string;
    description: string | null;
    amount: number;
    quantity: number | null;
    price: number | null;
    realized_gain: number | null;
  }[];
};

export default function AccountDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, error, loading, refetch } = useApi<AccountDetailPayload>(`/api/accounts/${id}`);

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(payload) => {
          const account = payload.account;
          const valuation = payload.valuation.result;

          return (
            <>
              <PageHeader
                breadcrumb={[{ label: "Accounts", href: "/accounts" }, { label: account.name }]}
                title={account.name}
                description={`${account.institution} · ${account.account_number_masked} · ${titleCase(account.registration)}`}
                meta={
                  <>
                    <Badge tone="outline">{titleCase(account.account_type)}</Badge>
                    {account.account_subtype ? <Badge tone="outline">{titleCase(account.account_subtype)}</Badge> : null}
                    {account.tax_treatment !== "n/a" ? <Badge tone="primary">{titleCase(account.tax_treatment)}</Badge> : null}
                    <FreshnessBadge status={account.data_freshness} label="Feed" />
                    {account.last_synced_at ? (
                      <span className="text-xs text-ink-muted">Synced {formatDate(account.last_synced_at)}</span>
                    ) : null}
                  </>
                }
              />

              {account.is_liability ? (
                <StatRow columns={3}>
                  <StatTile label="Outstanding balance" value={formatCurrency(account.balance)} tone="negative" />
                  <StatTile
                    label="Interest rate"
                    value={account.interest_rate ? formatPercent(account.interest_rate, { decimals: 2 }) : "—"}
                  />
                  <StatTile
                    label="Minimum payment"
                    value={account.minimum_payment ? formatCurrency(account.minimum_payment) : "—"}
                    hint="Per month"
                  />
                </StatRow>
              ) : (
                <StatRow columns={4}>
                  <StatTile label="Account value" value={formatCurrency(account.balance)} tone="primary" />
                  <StatTile
                    label="Invested"
                    value={formatCurrency(valuation.market_value - valuation.cash)}
                    hint={`${payload.holdings.length} positions`}
                  />
                  <StatTile label="Cash" value={formatCurrency(account.cash_balance)} hint="Available to invest" />
                  <StatTile
                    label="Unrealised gain"
                    value={formatCurrency(valuation.unrealized_gain, { compact: true })}
                    deltaPercent={valuation.unrealized_gain_percent}
                  />
                </StatRow>
              )}

              <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
                <Card>
                  <CardHeader title="Holdings" description={`${payload.holdings.length} positions in this account.`} />
                  {payload.holdings.length === 0 ? (
                    <EmptyState
                      title="No securities in this account"
                      description={
                        account.is_liability
                          ? "Liability accounts hold a balance rather than positions."
                          : "This account holds cash only."
                      }
                    />
                  ) : (
                    <Table>
                      <THead>
                        <TR>
                          <TH>Security</TH>
                          <TH align="right">Quantity</TH>
                          <TH align="right">Price</TH>
                          <TH align="right">Market value</TH>
                          <TH align="right">Gain/loss</TH>
                        </TR>
                      </THead>
                      <tbody>
                        {payload.holdings.map((holding) => (
                          <TR key={holding.holding_id}>
                            <TD>
                              <span className="font-medium">{holding.symbol}</span>
                              <span className="mt-0.5 block max-w-[16rem] truncate text-xs text-ink-muted">{holding.name}</span>
                              <Badge tone="outline" size="sm" className="mt-1">
                                {holding.asset_class_label}
                              </Badge>
                            </TD>
                            <TD align="right" numeric>{formatNumber(holding.quantity, 2)}</TD>
                            <TD align="right" numeric>{formatCurrency(holding.price, { decimals: 2 })}</TD>
                            <TD align="right" numeric className="font-medium">{formatCurrency(holding.market_value)}</TD>
                            <TD align="right">
                              <span className={cn("tabular text-sm", holding.gain_loss >= 0 ? "text-positive" : "text-negative")}>
                                {formatCurrency(holding.gain_loss, { signed: true })}
                              </span>
                              <Delta percent={holding.gain_loss_percent} showIcon={false} className="mt-0.5 block" />
                            </TD>
                          </TR>
                        ))}
                      </tbody>
                    </Table>
                  )}
                </Card>

                <div className="space-y-6">
                  <Card>
                    <CardHeader title="Account details" />
                    <CardBody>
                      <KeyValue
                        columns={1}
                        items={[
                          { label: "Institution", value: account.institution },
                          { label: "Connection", value: titleCase(account.connection_type) },
                          { label: "Registration", value: titleCase(account.registration) },
                          { label: "Tax treatment", value: titleCase(account.tax_treatment) },
                          { label: "Currency", value: account.currency },
                          { label: "Status", value: titleCase(account.status) },
                          { label: "Opened", value: account.opened_on ? formatDate(account.opened_on) : "—" },
                          { label: "Data source", value: account.data_source },
                        ]}
                      />
                    </CardBody>
                  </Card>

                  {!account.is_liability ? (
                    <Card>
                      <CardHeader title="Valuation" />
                      <CardBody>
                        <KeyValue
                          columns={1}
                          items={[
                            { label: "Market value", value: formatCurrency(valuation.market_value) },
                            { label: "Cost basis", value: formatCurrency(valuation.cost_basis) },
                            { label: "Unrealised gain", value: formatCurrency(valuation.unrealized_gain, { signed: true }) },
                            { label: "Change today", value: formatCurrency(valuation.day_change, { signed: true }) },
                          ]}
                        />
                        <CalcDisclosure calculation={payload.valuation} className="mt-4" />
                      </CardBody>
                    </Card>
                  ) : null}
                </div>
              </div>

              <Card>
                <CardHeader title="Recent activity" description="The 25 most recent transactions recorded for this account." />
                {payload.transactions.length === 0 ? (
                  <EmptyState title="No transactions recorded" />
                ) : (
                  <Table>
                    <THead>
                      <TR>
                        <TH>Date</TH>
                        <TH>Type</TH>
                        <TH>Description</TH>
                        <TH align="right">Quantity</TH>
                        <TH align="right">Amount</TH>
                        <TH align="right">Realised gain</TH>
                      </TR>
                    </THead>
                    <tbody>
                      {payload.transactions.map((transaction) => (
                        <TR key={transaction.id}>
                          <TD className="whitespace-nowrap text-xs">{formatDate(transaction.trade_date)}</TD>
                          <TD>
                            <Badge tone={transaction.type === "sell" ? "warning" : transaction.type === "dividend" ? "positive" : "outline"} size="sm">
                              {titleCase(transaction.type)}
                            </Badge>
                          </TD>
                          <TD className="max-w-[18rem] truncate text-xs text-ink-muted">{transaction.description ?? "—"}</TD>
                          <TD align="right" numeric className="text-xs">
                            {transaction.quantity ? formatNumber(transaction.quantity, 2) : "—"}
                          </TD>
                          <TD align="right" numeric className="font-medium">{formatCurrency(transaction.amount, { signed: true })}</TD>
                          <TD align="right" numeric className={cn(transaction.realized_gain ? (transaction.realized_gain >= 0 ? "text-positive" : "text-negative") : "text-ink-subtle")}>
                            {transaction.realized_gain !== null ? formatCurrency(transaction.realized_gain, { signed: true }) : "—"}
                          </TD>
                        </TR>
                      ))}
                    </tbody>
                  </Table>
                )}
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
