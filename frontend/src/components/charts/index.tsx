"use client";

/**
 * Charts.
 *
 * Rules held across the product:
 *  - Categorical hues are assigned in a fixed order and never cycled; a
 *    seventh category folds into "Other".
 *  - One value axis. Never two y-scales on one plot.
 *  - Colour follows the entity, not its rank, so filtering never repaints
 *    the survivors.
 *  - Every plot carries a hover layer, and identity is never colour alone:
 *    two or more series always get a legend, and small sets get direct labels.
 *  - Series colours come from CSS custom properties, so the dark theme uses
 *    its own validated steps rather than an inverted light palette.
 */

import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatCurrency, formatDate, formatPercent, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Fixed categorical order. Index 0 is always the first series on any chart. */
export const SERIES = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
] as const;

export const MAX_SERIES = SERIES.length;

const GRID = "hsl(var(--chart-grid))";
const AXIS = "hsl(var(--chart-axis))";
const SURFACE = "hsl(var(--surface))";
const BENCHMARK = "hsl(var(--chart-benchmark))";

const axisProps = {
  stroke: AXIS,
  strokeWidth: 1,
  tickLine: false,
  axisLine: false,
  tick: { fill: AXIS, fontSize: 11 },
} as const;

/* --------------------------------------------------------------- Tooltip */

function TooltipShell({ title, rows }: { title?: string; rows: { label: string; value: string; color?: string }[] }) {
  return (
    <div className="pointer-events-none min-w-[10rem] rounded-md border border-border bg-surface px-3 py-2 shadow-pop">
      {title ? <p className="mb-1.5 text-2xs font-semibold uppercase tracking-[0.06em] text-ink-subtle">{title}</p> : null}
      <div className="space-y-1">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-4 text-xs">
            <span className="flex items-center gap-1.5 text-ink-muted">
              {row.color ? (
                <span className="size-2 rounded-[2px]" style={{ background: row.color }} aria-hidden />
              ) : null}
              {row.label}
            </span>
            <span className="font-medium tabular text-ink">{row.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ Empty guard */

function ChartFrame({
  height,
  hasData,
  emptyLabel = "No data available for this period",
  children,
  className,
}: {
  height: number;
  hasData: boolean;
  emptyLabel?: string;
  children: React.ReactElement;
  className?: string;
}) {
  if (!hasData) {
    return (
      <div
        className={cn("flex items-center justify-center rounded-md border border-dashed border-border", className)}
        style={{ height }}
      >
        <p className="text-xs text-ink-subtle">{emptyLabel}</p>
      </div>
    );
  }
  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------ Area trend */

/** A single measure over time. One series, so the title carries identity. */
export function TrendArea({
  data,
  xKey = "as_of",
  yKey = "value",
  height = 220,
  label = "Value",
  formatValue = (value: number) => formatCurrency(value, { compact: true }),
}: {
  data: Record<string, unknown>[];
  xKey?: string;
  yKey?: string;
  height?: number;
  label?: string;
  formatValue?: (value: number) => string;
}) {
  return (
    <ChartFrame height={height} hasData={data.length > 1}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.22} />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey={xKey}
          {...axisProps}
          minTickGap={44}
          tickFormatter={(value: string) => formatDate(value, "short")}
        />
        <YAxis {...axisProps} width={64} tickFormatter={(value: number) => formatValue(value)} />
        <Tooltip
          cursor={{ stroke: AXIS, strokeWidth: 1, strokeDasharray: "3 3" }}
          content={({ active, payload, label: point }) =>
            active && payload?.length ? (
              <TooltipShell
                title={formatDate(String(point))}
                rows={[{ label, value: formatValue(Number(payload[0].value)), color: "var(--chart-1)" }]}
              />
            ) : null
          }
        />
        <Area
          type="monotone"
          dataKey={yKey}
          stroke="var(--chart-1)"
          strokeWidth={2}
          fill="url(#trend-fill)"
          activeDot={{ r: 4, strokeWidth: 2, stroke: SURFACE }}
          dot={false}
        />
      </AreaChart>
    </ChartFrame>
  );
}

/* ------------------------------------------- Portfolio vs benchmark index */

/**
 * Two series on one axis, both indexed to 100 at the start of the window, which
 * is what makes the comparison legitimate without a second y-scale.
 */
export function IndexedComparison({
  data,
  height = 260,
  benchmarkName = "Benchmark",
}: {
  data: { as_of: string; portfolio_index: number; benchmark_index: number }[];
  height?: number;
  benchmarkName?: string;
}) {
  const rebased = React.useMemo(() => {
    if (!data.length) return [];
    const basePortfolio = data[0].portfolio_index || 100;
    const baseBenchmark = data[0].benchmark_index || 100;
    return data.map((point) => ({
      as_of: point.as_of,
      Portfolio: (point.portfolio_index / basePortfolio) * 100,
      [benchmarkName]: (point.benchmark_index / baseBenchmark) * 100,
    }));
  }, [data, benchmarkName]);

  return (
    <div>
      <ChartFrame height={height} hasData={rebased.length > 1}>
        <LineChart data={rebased} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="as_of"
            {...axisProps}
            minTickGap={48}
            tickFormatter={(value: string) => formatDate(value, "short")}
          />
          <YAxis
            {...axisProps}
            width={48}
            domain={["auto", "auto"]}
            tickFormatter={(value: number) => value.toFixed(0)}
          />
          <ReferenceLine y={100} stroke={GRID} strokeWidth={1} />
          <Tooltip
            cursor={{ stroke: AXIS, strokeWidth: 1, strokeDasharray: "3 3" }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipShell
                  title={formatDate(String(label))}
                  rows={payload.map((entry) => ({
                    label: String(entry.name),
                    value: `${Number(entry.value).toFixed(1)} (rebased to 100)`,
                    color: String(entry.color),
                  }))}
                />
              ) : null
            }
          />
          <Line
            type="monotone"
            dataKey="Portfolio"
            stroke="var(--chart-1)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: SURFACE }}
          />
          <Line
            type="monotone"
            dataKey={benchmarkName}
            stroke={BENCHMARK}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: SURFACE }}
          />
        </LineChart>
      </ChartFrame>
      <ChartLegend
        items={[
          { label: "Portfolio", color: "var(--chart-1)" },
          { label: benchmarkName, color: BENCHMARK, dashed: true },
        ]}
      />
    </div>
  );
}

/* --------------------------------------------------------------- Legend */

export function ChartLegend({
  items,
  className,
}: {
  items: { label: string; color: string; value?: string; dashed?: boolean }[];
  className?: string;
}) {
  return (
    <ul className={cn("mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5", className)}>
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-2 text-xs text-ink-muted">
          <span
            className={cn("h-0.5 w-4 rounded-full", item.dashed && "opacity-70")}
            style={{
              background: item.dashed
                ? `repeating-linear-gradient(90deg, ${item.color} 0 5px, transparent 5px 9px)`
                : item.color,
            }}
            aria-hidden
          />
          <span>{item.label}</span>
          {item.value ? <span className="font-medium tabular text-ink">{item.value}</span> : null}
        </li>
      ))}
    </ul>
  );
}

/* ---------------------------------------------------------------- Donut */

/**
 * Composition. The labelled legend beside it carries the value for every slice,
 * so identity and magnitude never depend on colour alone.
 */
export function AllocationDonut({
  data,
  height = 220,
  valueFormatter = (value: number) => formatCurrency(value, { compact: true }),
  centerLabel,
  centerValue,
}: {
  data: { label: string; value: number; weight: number }[];
  height?: number;
  valueFormatter?: (value: number) => string;
  centerLabel?: string;
  centerValue?: string;
}) {
  // Past six categories the tail folds into "Other" rather than inventing hues.
  const slices = React.useMemo(() => {
    if (data.length <= MAX_SERIES) return data;
    const head = data.slice(0, MAX_SERIES - 1);
    const tail = data.slice(MAX_SERIES - 1);
    return [
      ...head,
      {
        label: "Other",
        value: tail.reduce((total, row) => total + row.value, 0),
        weight: tail.reduce((total, row) => total + row.weight, 0),
      },
    ];
  }, [data]);

  return (
    <div className="grid items-center gap-5 sm:grid-cols-[minmax(0,200px)_1fr]">
      <div className="relative">
        <ChartFrame height={height} hasData={slices.length > 0}>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              innerRadius="62%"
              outerRadius="94%"
              paddingAngle={2}
              stroke={SURFACE}
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((slice, index) => (
                <Cell key={slice.label} fill={SERIES[index % MAX_SERIES]} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipShell
                    rows={[
                      {
                        label: String(payload[0].name),
                        value: `${valueFormatter(Number(payload[0].value))} · ${formatPercent(
                          (payload[0].payload as { weight: number }).weight,
                          { decimals: 1 },
                        )}`,
                        color: String((payload[0] as { payload?: { fill?: string } }).payload?.fill),
                      },
                    ]}
                  />
                ) : null
              }
            />
          </PieChart>
        </ChartFrame>
        {centerValue ? (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            {centerLabel ? <p className="text-2xs uppercase tracking-[0.07em] text-ink-subtle">{centerLabel}</p> : null}
            <p className="text-lg font-semibold tabular text-ink">{centerValue}</p>
          </div>
        ) : null}
      </div>

      {/* The legend doubles as the table view: every slice is labelled with its value. */}
      <ul className="space-y-2">
        {slices.map((slice, index) => (
          <li key={slice.label} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="size-2.5 shrink-0 rounded-[3px]"
                style={{ background: SERIES[index % MAX_SERIES] }}
                aria-hidden
              />
              <span className="truncate text-ink-muted">{slice.label}</span>
            </span>
            <span className="flex shrink-0 items-baseline gap-2.5">
              <span className="tabular text-xs text-ink-subtle">{valueFormatter(slice.value)}</span>
              <span className="w-12 text-right font-medium tabular text-ink">
                {formatPercent(slice.weight, { decimals: 1 })}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* --------------------------------------------------------- Diverging bars */

/**
 * Signed values against a zero baseline: a diverging pair with a neutral
 * midpoint, never a categorical hue per bar.
 */
export function DivergingBars({
  data,
  height = 200,
  formatValue = (value: number) => formatPercent(value, { decimals: 1, signed: true }),
}: {
  data: { label: string; value: number; band?: number }[];
  height?: number;
  formatValue?: (value: number) => string;
}) {
  const bound = Math.max(...data.map((row) => Math.abs(row.value)), 0.01) * 1.25;

  return (
    <div>
      <ChartFrame height={height} hasData={data.length > 0}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 4 }} barCategoryGap={6}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            domain={[-bound, bound]}
            {...axisProps}
            tickFormatter={(value: number) => formatPercent(value, { decimals: 0 })}
          />
          <YAxis type="category" dataKey="label" {...axisProps} width={120} />
          <ReferenceLine x={0} stroke={AXIS} strokeWidth={1} />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted))", fillOpacity: 0.5 }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipShell
                  title={String((payload[0].payload as { label: string }).label)}
                  rows={[
                    { label: "Drift vs target", value: formatValue(Number(payload[0].value)) },
                    ...((payload[0].payload as { band?: number }).band !== undefined
                      ? [
                          {
                            label: "Tolerance band",
                            value: `±${formatPercent((payload[0].payload as { band: number }).band, { decimals: 1 })}`,
                          },
                        ]
                      : []),
                  ]}
                />
              ) : null
            }
          />
          <Bar dataKey="value" radius={4} barSize={14}>
            {data.map((row) => (
              <Cell
                key={row.label}
                fill={row.value >= 0 ? "var(--chart-over)" : "var(--chart-under)"}
                stroke={SURFACE}
                strokeWidth={2}
              />
            ))}
          </Bar>
        </BarChart>
      </ChartFrame>
      <ChartLegend
        items={[
          { label: "Above target", color: "var(--chart-over)" },
          { label: "Below target", color: "var(--chart-under)" },
        ]}
      />
    </div>
  );
}

/* ---------------------------------------------------------- Stacked bars */

export function StackedBars({
  data,
  keys,
  xKey = "label",
  height = 240,
  formatValue = (value: number) => formatCurrency(value, { compact: true }),
}: {
  data: Record<string, unknown>[];
  keys: { key: string; label: string }[];
  xKey?: string;
  height?: number;
  formatValue?: (value: number) => string;
}) {
  const series = keys.slice(0, MAX_SERIES);

  return (
    <div>
      <ChartFrame height={height} hasData={data.length > 0}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="22%">
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={xKey} {...axisProps} minTickGap={16} />
          <YAxis {...axisProps} width={62} tickFormatter={formatValue} />
          <Tooltip
            cursor={{ fill: "hsl(var(--muted))", fillOpacity: 0.5 }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipShell
                  title={String(label)}
                  rows={[
                    ...payload.map((entry) => ({
                      label: String(entry.name),
                      value: formatValue(Number(entry.value)),
                      color: String(entry.color),
                    })),
                    {
                      label: "Total",
                      value: formatValue(payload.reduce((total, entry) => total + Number(entry.value ?? 0), 0)),
                    },
                  ]}
                />
              ) : null
            }
          />
          {series.map((entry, index) => (
            <Bar
              key={entry.key}
              dataKey={entry.key}
              name={entry.label}
              stackId="stack"
              fill={SERIES[index]}
              stroke={SURFACE}
              strokeWidth={2}
              radius={index === series.length - 1 ? [4, 4, 0, 0] : 0}
            />
          ))}
        </BarChart>
      </ChartFrame>
      <ChartLegend items={series.map((entry, index) => ({ label: entry.label, color: SERIES[index] }))} />
    </div>
  );
}

/* ------------------------------------------------------------ Simple bars */

export function CategoryBars({
  data,
  height = 220,
  formatValue = (value: number) => formatNumber(value),
  seriesLabel = "Count",
}: {
  data: { label: string; value: number }[];
  height?: number;
  formatValue?: (value: number) => string;
  seriesLabel?: string;
}) {
  return (
    <ChartFrame height={height} hasData={data.length > 0}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="26%">
        <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" {...axisProps} />
        <YAxis {...axisProps} width={52} tickFormatter={formatValue} />
        <Tooltip
          cursor={{ fill: "hsl(var(--muted))", fillOpacity: 0.5 }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <TooltipShell
                title={String(label)}
                rows={[{ label: seriesLabel, value: formatValue(Number(payload[0].value)), color: "var(--chart-1)" }]}
              />
            ) : null
          }
        />
        <Bar dataKey="value" fill="var(--chart-1)" radius={[4, 4, 0, 0]} maxBarSize={56} />
      </BarChart>
    </ChartFrame>
  );
}

/* ------------------------------------------------------- Percentile band */

/**
 * A Monte Carlo outcome range: the band is the 10th-90th percentile, the line
 * is the median. Shading is a single hue at two opacities, not two hues.
 */
export function PercentileBand({
  data,
  height = 240,
}: {
  data: { label: string; p10: number; p50: number; p90: number }[];
  height?: number;
}) {
  const shaped = data.map((row) => ({ ...row, span: row.p90 - row.p10 }));

  return (
    <div>
      <ChartFrame height={height} hasData={shaped.length > 0}>
        <AreaChart data={shaped} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" {...axisProps} minTickGap={24} />
          <YAxis
            {...axisProps}
            width={64}
            tickFormatter={(value: number) => formatCurrency(value, { compact: true })}
          />
          <Tooltip
            cursor={{ stroke: AXIS, strokeWidth: 1, strokeDasharray: "3 3" }}
            content={({ active, payload, label }) =>
              active && payload?.length ? (
                <TooltipShell
                  title={String(label)}
                  rows={[
                    { label: "90th percentile", value: formatCurrency((payload[0].payload as { p90: number }).p90, { compact: true }) },
                    { label: "Median", value: formatCurrency((payload[0].payload as { p50: number }).p50, { compact: true }), color: "var(--chart-1)" },
                    { label: "10th percentile", value: formatCurrency((payload[0].payload as { p10: number }).p10, { compact: true }) },
                  ]}
                />
              ) : null
            }
          />
          <Area dataKey="p10" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
          <Area
            dataKey="span"
            stackId="band"
            stroke="none"
            fill="var(--chart-1)"
            fillOpacity={0.16}
            isAnimationActive={false}
          />
          <Line type="monotone" dataKey="p50" stroke="var(--chart-1)" strokeWidth={2} dot={false} />
        </AreaChart>
      </ChartFrame>
      <ChartLegend
        items={[
          { label: "Median outcome", color: "var(--chart-1)" },
          { label: "10th–90th percentile range", color: "var(--chart-1)" },
        ]}
      />
    </div>
  );
}

/* ------------------------------------------------------------- Scatter-ish */

/** Efficient frontier: risk on x, return on y, with the current portfolio marked. */
export function FrontierChart({
  frontier,
  current,
  height = 260,
}: {
  frontier: { volatility: number; expected_return: number; label: string }[];
  current?: { volatility: number; expected_return: number; label: string } | null;
  height?: number;
}) {
  const data = frontier.map((point) => ({ ...point, x: point.volatility, y: point.expected_return }));

  return (
    <div>
      <ChartFrame height={height} hasData={data.length > 0}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis
            dataKey="x"
            type="number"
            {...axisProps}
            domain={["dataMin - 0.01", "dataMax + 0.01"]}
            tickFormatter={(value: number) => formatPercent(value, { decimals: 0 })}
            label={{ value: "Expected volatility", position: "insideBottom", offset: -6, fill: AXIS, fontSize: 11 }}
          />
          <YAxis
            dataKey="y"
            type="number"
            {...axisProps}
            width={52}
            domain={["dataMin - 0.005", "dataMax + 0.005"]}
            tickFormatter={(value: number) => formatPercent(value, { decimals: 0 })}
          />
          <Tooltip
            cursor={{ stroke: AXIS, strokeWidth: 1, strokeDasharray: "3 3" }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <TooltipShell
                  title={String((payload[0].payload as { label: string }).label)}
                  rows={[
                    { label: "Expected return", value: formatPercent((payload[0].payload as { y: number }).y) },
                    { label: "Volatility", value: formatPercent((payload[0].payload as { x: number }).x) },
                  ]}
                />
              ) : null
            }
          />
          <Line
            type="monotone"
            dataKey="y"
            stroke="var(--chart-1)"
            strokeWidth={2}
            dot={{ r: 3, fill: "var(--chart-1)", stroke: SURFACE, strokeWidth: 2 }}
            activeDot={{ r: 5, strokeWidth: 2, stroke: SURFACE }}
          />
          {current ? (
            <ReferenceLine
              x={current.volatility}
              stroke="var(--chart-2)"
              strokeWidth={2}
              strokeDasharray="4 4"
              label={{ value: "Current", fill: "var(--chart-2)", fontSize: 11, position: "top" }}
            />
          ) : null}
        </LineChart>
      </ChartFrame>
      <ChartLegend
        items={[
          { label: "Efficient frontier", color: "var(--chart-1)" },
          ...(current
            ? [
                {
                  label: `Current portfolio · ${formatPercent(current.expected_return)} return at ${formatPercent(current.volatility)} risk`,
                  color: "var(--chart-2)",
                  dashed: true,
                },
              ]
            : []),
        ]}
      />
    </div>
  );
}
