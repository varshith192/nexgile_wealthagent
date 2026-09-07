"use client";

/** Holdings grid (§13): search, sort, filter, paginate and a detail drawer. */

import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatNumber, formatPercent } from "@/lib/format";
import type { HoldingRow } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardHeader, Drawer, Input, Select, TD, TH, THead, TR, Table } from "@/components/ui";
import { Delta, FreshnessBadge } from "@/components/shared/indicators";
import { KeyValue, PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingTable, NoResults } from "@/components/shared/states";

type HoldingsPayload = {
  rows: HoldingRow[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  as_of: string;
  totals: { market_value: number; cost_basis: number; gain_loss: number; day_change: number };
};

type HoldingDetail = {
  holding_id: string;
  account: { id: string; name: string; type: string };
  security: {
    symbol: string;
    name: string;
    security_type: string;
    asset_class_label: string;
    sector: string;
    region: string;
    last_price: number;
    previous_close: number;
    dividend_yield: number;
    expense_ratio: number | null;
    beta: number;
    volatility: number;
    esg_score: number | null;
    price_status: string;
    price_as_of: string | null;
  };
  quantity: number;
  market_value: number;
  cost_basis: number;
  gain_loss: number;
  gain_loss_percent: number;
  day_change: number;
  day_change_percent: number;
  annual_income: number;
  tax_lots: {
    id: string;
    quantity: number;
    cost_per_share: number;
    cost_basis: number;
    market_value: number;
    gain_loss: number;
    acquired_on: string;
    holding_period: string;
    washed: boolean;
  }[];
};

const COLUMNS: { key: string; label: string; align: "left" | "right"; sortable: boolean }[] = [
  { key: "symbol", label: "Security", align: "left", sortable: true },
  { key: "quantity", label: "Quantity", align: "right", sortable: true },
  { key: "price", label: "Price", align: "right", sortable: true },
  { key: "market_value", label: "Market value", align: "right", sortable: true },
  { key: "cost_basis", label: "Cost basis", align: "right", sortable: true },
  { key: "gain_loss", label: "Gain/loss", align: "right", sortable: true },
  { key: "gain_loss_percent", label: "Gain/loss %", align: "right", sortable: true },
  { key: "weight", label: "Weight", align: "right", sortable: true },
  { key: "asset_class", label: "Asset class", align: "left", sortable: true },
];

const ASSET_CLASSES = [
  { value: "", label: "All asset classes" },
  { value: "us_equity", label: "US Equity" },
  { value: "intl_equity", label: "International Equity" },
  { value: "fixed_income", label: "Fixed Income" },
  { value: "cash", label: "Cash" },
  { value: "alternatives", label: "Alternatives" },
  { value: "real_assets", label: "Real Assets" },
];

export default function HoldingsPage() {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [assetClass, setAssetClass] = useState("");
  const [sortBy, setSortBy] = useState("market_value");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [search]);

  const path = useMemo(() => {
    const params = new URLSearchParams({
      sort_by: sortBy,
      sort_dir: sortDir,
      page: String(page),
      page_size: String(pageSize),
    });
    if (debounced) params.set("search", debounced);
    if (assetClass) params.set("asset_class", assetClass);
    return `/api/holdings?${params.toString()}`;
  }, [debounced, assetClass, sortBy, sortDir, page, pageSize]);

  const { data, error, loading, refetch } = useApi<HoldingsPayload>(path);

  const toggleSort = (key: string) => {
    if (sortBy === key) {
      setSortDir((direction) => (direction === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setSortDir("desc");
    }
    setPage(1);
  };

  const clearFilters = () => {
    setSearch("");
    setAssetClass("");
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Holdings"
        description="Every position across all managed accounts, with cost basis and unrealised gain."
        meta={data ? <span className="text-xs text-ink-muted">As of {formatDate(data.as_of)}</span> : undefined}
      />

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Positions" value={formatNumber(data.total)} hint={`${data.pages} page${data.pages === 1 ? "" : "s"}`} />
          <StatTile label="Market value" value={formatCurrency(data.totals.market_value, { compact: true })} tone="primary" />
          <StatTile label="Cost basis" value={formatCurrency(data.totals.cost_basis, { compact: true })} />
          <StatTile
            label="Unrealised gain"
            value={formatCurrency(data.totals.gain_loss, { compact: true })}
            delta={data.totals.day_change}
            hint="Change today"
          />
        </StatRow>
      ) : null}

      <Card>
        <CardHeader
          title="Positions"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-subtle" aria-hidden />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search symbol or name"
                  className="h-8 w-52 pl-8 text-xs"
                  aria-label="Search holdings"
                />
              </div>
              <Select
                value={assetClass}
                onChange={(event) => {
                  setAssetClass(event.target.value);
                  setPage(1);
                }}
                className="h-8 w-48 text-xs"
                aria-label="Filter by asset class"
              >
                {ASSET_CLASSES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
              <Select
                value={String(pageSize)}
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
                className="h-8 w-28 text-xs"
                aria-label="Rows per page"
              >
                {[25, 50, 100].map((size) => (
                  <option key={size} value={size}>
                    {size} rows
                  </option>
                ))}
              </Select>
              {(debounced || assetClass) && (
                <Button size="sm" variant="ghost" onClick={clearFilters}>
                  <SlidersHorizontal />
                  Clear
                </Button>
              )}
            </div>
          }
        />

        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={8} />}
          emptyWhen={(payload) => payload.rows.length === 0}
          empty={<NoResults query={debounced} onClear={clearFilters} />}
        >
          {(payload) => (
            <>
              <Table>
                <THead>
                  <TR className="hover:bg-transparent">
                    {COLUMNS.map((column) => (
                      <TH key={column.key} align={column.align}>
                        {column.sortable ? (
                          <button
                            onClick={() => toggleSort(column.key)}
                            className={cn(
                              "inline-flex items-center gap-1 transition-colors hover:text-ink",
                              sortBy === column.key && "text-ink",
                            )}
                          >
                            {column.label}
                            {sortBy === column.key ? (
                              sortDir === "asc" ? (
                                <ArrowUp className="size-3" aria-hidden />
                              ) : (
                                <ArrowDown className="size-3" aria-hidden />
                              )
                            ) : null}
                          </button>
                        ) : (
                          column.label
                        )}
                      </TH>
                    ))}
                  </TR>
                </THead>
                <tbody>
                  {payload.rows.map((row) => (
                    <TR
                      key={row.holding_id}
                      className="cursor-pointer"
                      onClick={() => setSelected(row.holding_id)}
                      tabIndex={0}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") setSelected(row.holding_id);
                      }}
                    >
                      <TD>
                        <span className="flex items-center gap-2">
                          <span className="font-medium text-ink">{row.symbol}</span>
                          {row.price_status !== "fresh" ? (
                            <Badge tone="warning" size="sm">
                              {row.price_status}
                            </Badge>
                          ) : null}
                        </span>
                        <span className="mt-0.5 block max-w-[18rem] truncate text-xs text-ink-muted">{row.name}</span>
                        <span className="mt-0.5 block text-2xs text-ink-subtle">{row.account_name}</span>
                      </TD>
                      <TD align="right" numeric>{formatNumber(row.quantity, 2)}</TD>
                      <TD align="right" numeric>{formatCurrency(row.price, { decimals: 2 })}</TD>
                      <TD align="right" numeric className="font-medium">{formatCurrency(row.market_value)}</TD>
                      <TD align="right" numeric className="text-ink-muted">{formatCurrency(row.cost_basis)}</TD>
                      <TD align="right" numeric className={row.gain_loss >= 0 ? "text-positive" : "text-negative"}>
                        {formatCurrency(row.gain_loss, { signed: true })}
                      </TD>
                      <TD align="right">
                        <Delta percent={row.gain_loss_percent} showIcon={false} />
                      </TD>
                      <TD align="right" numeric>{formatPercent(row.weight, { decimals: 2 })}</TD>
                      <TD>
                        <Badge tone="outline" size="sm">
                          {row.asset_class_label}
                        </Badge>
                      </TD>
                    </TR>
                  ))}
                </tbody>
              </Table>

              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-3">
                <p className="text-xs text-ink-muted">
                  Showing{" "}
                  <span className="font-medium tabular text-ink">
                    {(payload.page - 1) * payload.page_size + 1}–
                    {Math.min(payload.page * payload.page_size, payload.total)}
                  </span>{" "}
                  of <span className="font-medium tabular text-ink">{formatNumber(payload.total)}</span> positions
                </p>
                <div className="flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={payload.page <= 1}
                    onClick={() => setPage((current) => Math.max(current - 1, 1))}
                  >
                    <ChevronLeft />
                    Previous
                  </Button>
                  <span className="px-2 text-xs tabular text-ink-muted">
                    Page {payload.page} of {payload.pages}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={payload.page >= payload.pages}
                    onClick={() => setPage((current) => current + 1)}
                  >
                    Next
                    <ChevronRight />
                  </Button>
                </div>
              </div>
            </>
          )}
        </DataState>
      </Card>

      <HoldingDrawer holdingId={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function HoldingDrawer({ holdingId, onClose }: { holdingId: string | null; onClose: () => void }) {
  const [detail, setDetail] = useState<HoldingDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!holdingId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    api
      .get<HoldingDetail>(`/api/holdings/${holdingId}`)
      .then(setDetail)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [holdingId]);

  return (
    <Drawer
      open={Boolean(holdingId)}
      onClose={onClose}
      title={detail ? `${detail.security.symbol} · ${detail.security.name}` : "Holding"}
      description={detail ? `${detail.account.name} · ${detail.security.asset_class_label}` : undefined}
    >
      <DataState loading={loading} error={error} data={detail}>
        {(row) => (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <Metric label="Market value" value={formatCurrency(row.market_value)} />
              <Metric label="Unrealised gain" value={formatCurrency(row.gain_loss, { signed: true })} tone={row.gain_loss >= 0 ? "positive" : "negative"} />
              <Metric label="Quantity" value={formatNumber(row.quantity, 4)} />
              <Metric label="Change today" value={formatCurrency(row.day_change, { signed: true })} tone={row.day_change >= 0 ? "positive" : "negative"} />
            </div>

            <section>
              <h3 className="section-label">Position</h3>
              <KeyValue
                className="mt-2.5"
                items={[
                  { label: "Cost basis", value: formatCurrency(row.cost_basis) },
                  { label: "Gain/loss %", value: formatPercent(row.gain_loss_percent) },
                  { label: "Last price", value: formatCurrency(row.security.last_price, { decimals: 2 }) },
                  { label: "Previous close", value: formatCurrency(row.security.previous_close, { decimals: 2 }) },
                  { label: "Forward income", value: formatCurrency(row.annual_income) },
                  { label: "Distribution yield", value: formatPercent(row.security.dividend_yield, { decimals: 2 }) },
                ]}
              />
            </section>

            <section>
              <h3 className="section-label">Security</h3>
              <KeyValue
                className="mt-2.5"
                items={[
                  { label: "Type", value: row.security.security_type.toUpperCase() },
                  { label: "Asset class", value: row.security.asset_class_label },
                  { label: "Sector", value: row.security.sector },
                  { label: "Region", value: row.security.region },
                  { label: "Beta", value: row.security.beta.toFixed(2) },
                  { label: "Volatility", value: formatPercent(row.security.volatility, { decimals: 1 }) },
                  {
                    label: "Expense ratio",
                    value: row.security.expense_ratio !== null ? formatPercent(row.security.expense_ratio, { decimals: 2 }) : "n/a",
                  },
                  { label: "ESG score", value: row.security.esg_score !== null ? row.security.esg_score.toFixed(0) : "Not rated" },
                ]}
              />
              <div className="mt-3 flex items-center gap-2">
                <FreshnessBadge status={row.security.price_status as "fresh" | "delayed" | "stale" | "unavailable"} label="Price" />
                {row.security.price_as_of ? (
                  <span className="text-xs text-ink-muted">Priced {formatDate(row.security.price_as_of)}</span>
                ) : null}
              </div>
            </section>

            <section>
              <h3 className="section-label">Tax lots</h3>
              <p className="mt-1 text-xs text-ink-muted">
                Open lots only. Holding period determines whether a sale is taxed at short- or long-term rates.
              </p>
              <div className="mt-3 overflow-hidden rounded-md border border-border">
                <Table>
                  <THead>
                    <TR>
                      <TH>Acquired</TH>
                      <TH align="right">Quantity</TH>
                      <TH align="right">Cost</TH>
                      <TH align="right">Gain/loss</TH>
                      <TH>Period</TH>
                    </TR>
                  </THead>
                  <tbody>
                    {row.tax_lots.map((lot) => (
                      <TR key={lot.id}>
                        <TD className="text-xs">{formatDate(lot.acquired_on)}</TD>
                        <TD align="right" numeric className="text-xs">{formatNumber(lot.quantity, 2)}</TD>
                        <TD align="right" numeric className="text-xs">{formatCurrency(lot.cost_basis)}</TD>
                        <TD align="right" numeric className={cn("text-xs", lot.gain_loss >= 0 ? "text-positive" : "text-negative")}>
                          {formatCurrency(lot.gain_loss, { signed: true })}
                        </TD>
                        <TD>
                          <Badge tone={lot.holding_period === "long_term" ? "positive" : "neutral"} size="sm">
                            {lot.holding_period === "long_term" ? "Long" : "Short"}
                          </Badge>
                        </TD>
                      </TR>
                    ))}
                  </tbody>
                </Table>
              </div>
            </section>
          </div>
        )}
      </DataState>
    </Drawer>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "positive" | "negative" }) {
  const toneClass = { neutral: "text-ink", positive: "text-positive", negative: "text-negative" }[tone];
  return (
    <div className="rounded-md border border-border bg-surface-muted/60 p-3.5">
      <p className="section-label">{label}</p>
      <p className={cn("mt-1 text-lg font-semibold tabular", toneClass)}>{value}</p>
    </div>
  );
}
