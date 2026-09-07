"use client";

/** Accounts (§11): every linked account, grouped by type, with freshness. */

import { useState } from "react";
import Link from "next/link";
import { Building2, ChevronRight, Landmark, Wallet } from "lucide-react";

import { formatCurrency, formatDate, formatPercent, formatRelative, titleCase } from "@/lib/format";
import type { AccountRow, Freshness } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardHeader, Tabs } from "@/components/ui";
import { AllocationDonut } from "@/components/charts";
import { FreshnessBadge, FreshnessBar } from "@/components/shared/indicators";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type AccountsPayload = {
  accounts: AccountRow[];
  summary: {
    total_assets: number;
    total_liabilities: number;
    net_worth: number;
    account_count: number;
    external_count: number;
    by_type: { account_type: string; count: number; balance: number }[];
  };
  data_freshness: Record<string, Freshness>;
  as_of: string;
};

const TYPE_LABEL: Record<string, string> = {
  brokerage: "Brokerage",
  retirement: "Retirement",
  trust: "Trust",
  education: "Education",
  banking: "Banking",
  credit: "Credit",
  mortgage: "Mortgage",
  external: "External",
};

export default function AccountsPage() {
  const { data, error, loading, refetch } = useApi<AccountsPayload>("/api/accounts");
  const [tab, setTab] = useState("all");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        description="Every account linked to your household, including liabilities and externally held assets."
        meta={data ? <FreshnessBar freshness={data.data_freshness} asOf={data.as_of} /> : undefined}
      />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(payload) => {
          const assets = payload.accounts.filter((account) => !account.is_liability);
          const liabilities = payload.accounts.filter((account) => account.is_liability);
          const visible = tab === "all" ? payload.accounts : tab === "assets" ? assets : liabilities;

          const grouped = visible.reduce<Record<string, AccountRow[]>>((groups, account) => {
            (groups[account.account_type] ||= []).push(account);
            return groups;
          }, {});

          return (
            <>
              <StatRow columns={4}>
                <StatTile label="Net worth" value={formatCurrency(payload.summary.net_worth, { compact: true })} tone="primary" icon={Wallet} />
                <StatTile label="Total assets" value={formatCurrency(payload.summary.total_assets, { compact: true })} hint={`${assets.length} accounts`} icon={Landmark} />
                <StatTile label="Total liabilities" value={formatCurrency(payload.summary.total_liabilities, { compact: true })} hint={`${liabilities.length} accounts`} />
                <StatTile
                  label="Linked institutions"
                  value={String(new Set(payload.accounts.map((account) => account.institution)).size)}
                  hint={`${payload.summary.external_count} externally held`}
                  icon={Building2}
                />
              </StatRow>

              <div className="grid gap-6 xl:grid-cols-[1fr_1.6fr]">
                <Card>
                  <CardHeader title="Balance by account type" description="Liabilities are shown as negative balances." />
                  <div className="p-5">
                    <AllocationDonut
                      data={payload.summary.by_type
                        .filter((row) => row.balance > 0)
                        .map((row) => ({
                          label: TYPE_LABEL[row.account_type] ?? titleCase(row.account_type),
                          value: row.balance,
                          weight: row.balance / payload.summary.total_assets,
                        }))}
                      height={210}
                      centerLabel="Assets"
                      centerValue={formatCurrency(payload.summary.total_assets, { compact: true })}
                    />
                  </div>
                </Card>

                <Card>
                  <CardHeader title="Data connections" description="Where each balance comes from and how current it is (§39)." />
                  <ul className="divide-y divide-border">
                    {Array.from(new Set(payload.accounts.map((account) => account.institution))).map((institution) => {
                      const accounts = payload.accounts.filter((account) => account.institution === institution);
                      const worst = accounts.reduce<Freshness>((current, account) => {
                        const order: Freshness[] = ["unavailable", "stale", "delayed", "fresh"];
                        return order.indexOf(account.data_freshness) < order.indexOf(current) ? account.data_freshness : current;
                      }, "fresh");
                      const lastSync = accounts
                        .map((account) => account.last_synced_at)
                        .filter(Boolean)
                        .sort()
                        .reverse()[0];
                      return (
                        <li key={institution} className="flex items-center justify-between gap-4 px-5 py-3">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-ink">{institution}</p>
                            <p className="mt-0.5 text-xs text-ink-muted">
                              {accounts.length} account{accounts.length === 1 ? "" : "s"} ·{" "}
                              {titleCase(accounts[0].connection_type)}
                              {lastSync ? ` · updated ${formatRelative(lastSync)}` : ""}
                            </p>
                          </div>
                          <FreshnessBadge status={worst} />
                        </li>
                      );
                    })}
                  </ul>
                </Card>
              </div>

              <Card>
                <CardHeader title="All accounts" />
                <div className="px-5">
                  <Tabs
                    value={tab}
                    onChange={setTab}
                    tabs={[
                      { value: "all", label: "All", count: payload.accounts.length },
                      { value: "assets", label: "Assets", count: assets.length },
                      { value: "liabilities", label: "Liabilities", count: liabilities.length },
                    ]}
                  />
                </div>

                {visible.length === 0 ? (
                  <EmptyState title="No accounts in this view" />
                ) : (
                  <div className="divide-y divide-border">
                    {Object.entries(grouped).map(([type, accounts]) => (
                      <div key={type}>
                        <div className="flex items-center justify-between gap-3 bg-surface-muted/60 px-5 py-2">
                          <p className="text-2xs font-semibold uppercase tracking-[0.08em] text-ink-subtle">
                            {TYPE_LABEL[type] ?? titleCase(type)}
                          </p>
                          <p className="text-xs tabular text-ink-muted">
                            {formatCurrency(
                              accounts.reduce((total, account) => total + (account.is_liability ? -account.balance : account.balance), 0),
                              { compact: true },
                            )}
                          </p>
                        </div>
                        <ul className="divide-y divide-border">
                          {accounts.map((account) => (
                            <li key={account.id}>
                              <Link
                                href={`/accounts/${account.id}`}
                                className="flex items-center justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-surface-muted/70"
                              >
                                <div className="min-w-0">
                                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                                    {account.name}
                                    {account.is_external ? <Badge tone="outline" size="sm">External</Badge> : null}
                                    {account.tax_treatment !== "n/a" ? (
                                      <Badge tone="outline" size="sm">{titleCase(account.tax_treatment)}</Badge>
                                    ) : null}
                                  </p>
                                  <p className="mt-0.5 text-xs text-ink-muted">
                                    {account.institution} · {account.account_number_masked}
                                    {account.interest_rate ? ` · ${formatPercent(account.interest_rate, { decimals: 2 })} rate` : ""}
                                    {account.opened_on ? ` · opened ${formatDate(account.opened_on)}` : ""}
                                  </p>
                                </div>
                                <div className="flex shrink-0 items-center gap-4">
                                  <div className="text-right">
                                    <p
                                      className={`text-sm font-semibold tabular ${account.is_liability ? "text-negative" : "text-ink"}`}
                                    >
                                      {account.is_liability ? "−" : ""}
                                      {formatCurrency(account.balance)}
                                    </p>
                                    {account.cash_balance > 0 ? (
                                      <p className="mt-0.5 text-xs tabular text-ink-subtle">
                                        {formatCurrency(account.cash_balance)} cash
                                      </p>
                                    ) : null}
                                  </div>
                                  <FreshnessBadge status={account.data_freshness} />
                                  <ChevronRight className="size-4 text-ink-subtle" aria-hidden />
                                </div>
                              </Link>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
