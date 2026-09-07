"use client";

/**
 * Status vocabulary: badges, freshness, deltas and calculation disclosure.
 *
 * Every status in the product is expressed through these components, so
 * "at risk" looks the same on the dashboard, the goal page and the advisor
 * workstation.
 */

import { useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronRight,
  CircleCheck,
  CircleDashed,
  CircleDot,
  Info,
  Minus,
  TriangleAlert,
  WifiOff,
} from "lucide-react";

import { formatCurrency, formatDate, formatPercent, titleCase, trendTone } from "@/lib/format";
import type { Calculation, Freshness, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge, InfoTip } from "@/components/ui";

/* -------------------------------------------------------------- Severity */

const SEVERITY_TONE: Record<Severity, "neutral" | "info" | "warning" | "negative" | "primary"> = {
  info: "info",
  low: "neutral",
  medium: "warning",
  high: "negative",
  critical: "negative",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge tone={SEVERITY_TONE[severity] ?? "neutral"}>{severity}</Badge>;
}

/* ------------------------------------------------------------ Goal status */

const GOAL_STATUS: Record<string, { tone: "positive" | "warning" | "negative" | "neutral"; label: string }> = {
  on_track: { tone: "positive", label: "On track" },
  monitor: { tone: "neutral", label: "Monitor" },
  at_risk: { tone: "warning", label: "At risk" },
  off_track: { tone: "negative", label: "Off track" },
};

export function GoalStatusBadge({ status }: { status: string }) {
  const config = GOAL_STATUS[status] ?? { tone: "neutral" as const, label: titleCase(status) };
  return <Badge tone={config.tone}>{config.label}</Badge>;
}

/* -------------------------------------------------------- Approval status */

const APPROVAL_STATUS: Record<string, { tone: "neutral" | "info" | "warning" | "positive" | "negative"; label: string }> = {
  draft: { tone: "neutral", label: "Draft" },
  submitted: { tone: "info", label: "Submitted" },
  under_review: { tone: "warning", label: "Under review" },
  approved: { tone: "positive", label: "Approved" },
  rejected: { tone: "negative", label: "Rejected" },
  cancelled: { tone: "neutral", label: "Cancelled" },
  completed: { tone: "positive", label: "Completed" },
  pending_review: { tone: "warning", label: "Pending review" },
  identified: { tone: "info", label: "Identified" },
  proposed: { tone: "info", label: "Proposed" },
  executed: { tone: "positive", label: "Executed" },
  complete: { tone: "positive", label: "Complete" },
  at_risk: { tone: "warning", label: "At risk" },
  pending: { tone: "neutral", label: "Pending" },
  overdue: { tone: "negative", label: "Overdue" },
  open: { tone: "info", label: "Open" },
  in_progress: { tone: "warning", label: "In progress" },
  pass: { tone: "positive", label: "Pass" },
  fail: { tone: "negative", label: "Fail" },
  watch: { tone: "warning", label: "Watch" },
  replace: { tone: "negative", label: "Replace" },
  active: { tone: "positive", label: "Active" },
  clear: { tone: "positive", label: "Clear" },
  blocked: { tone: "negative", label: "Blocked" },
  reviewed: { tone: "positive", label: "Reviewed" },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const config = APPROVAL_STATUS[status] ?? { tone: "neutral" as const, label: titleCase(status) };
  return (
    <Badge tone={config.tone} className={className}>
      {config.label}
    </Badge>
  );
}

/* ---------------------------------------------------------- Data freshness */

const FRESHNESS: Record<Freshness, { tone: "positive" | "warning" | "negative" | "neutral"; label: string; hint: string }> = {
  fresh: { tone: "positive", label: "Fresh", hint: "Updated within the last 24 hours." },
  delayed: { tone: "warning", label: "Delayed", hint: "Last update was more than 24 hours ago." },
  stale: { tone: "negative", label: "Stale", hint: "Last update was more than 3 days ago. Treat these figures as indicative." },
  unavailable: { tone: "neutral", label: "Unavailable", hint: "No update has been received from this source." },
};

const FRESHNESS_ICON: Record<Freshness, React.ComponentType<{ className?: string }>> = {
  fresh: CircleCheck,
  delayed: CircleDot,
  stale: TriangleAlert,
  unavailable: WifiOff,
};

export function FreshnessBadge({ status, label }: { status: Freshness; label?: string }) {
  const config = FRESHNESS[status] ?? FRESHNESS.unavailable;
  const Icon = FRESHNESS_ICON[status] ?? CircleDashed;
  return (
    <InfoTip label={config.hint}>
      <Badge tone={config.tone} className="cursor-help">
        <Icon className="size-3" />
        {label ? `${label}: ${config.label}` : config.label}
      </Badge>
    </InfoTip>
  );
}

export function FreshnessBar({ freshness, asOf }: { freshness: Record<string, Freshness>; asOf?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {asOf ? (
        <span className="text-xs text-ink-muted">
          As of <span className="font-medium text-ink">{formatDate(asOf)}</span>
        </span>
      ) : null}
      {Object.entries(freshness).map(([source, status]) => (
        <FreshnessBadge key={source} status={status} label={titleCase(source)} />
      ))}
    </div>
  );
}

/* -------------------------------------------------------------- Delta text */

export function Delta({
  value,
  percent,
  className,
  showIcon = true,
  size = "sm",
}: {
  value?: number | null;
  percent?: number | null;
  className?: string;
  showIcon?: boolean;
  size?: "sm" | "md" | "lg";
}) {
  const basis = value ?? percent ?? 0;
  const tone = trendTone(basis);
  const Icon = tone === "positive" ? ArrowUpRight : tone === "negative" ? ArrowDownRight : Minus;

  const toneClass = {
    positive: "text-positive",
    negative: "text-negative",
    neutral: "text-ink-muted",
  }[tone];

  const sizeClass = { sm: "text-xs", md: "text-sm", lg: "text-base" }[size];

  return (
    <span className={cn("inline-flex items-center gap-1 font-medium tabular", toneClass, sizeClass, className)}>
      {showIcon ? <Icon className="size-3.5" aria-hidden /> : null}
      {value !== undefined && value !== null ? formatCurrency(value, { compact: true, signed: true }) : null}
      {value !== undefined && value !== null && percent !== undefined && percent !== null ? " · " : null}
      {percent !== undefined && percent !== null ? formatPercent(percent, { signed: true }) : null}
    </span>
  );
}

/* --------------------------------------------------- Calculation disclosure */

/**
 * §4: every figure can show its own working — method, inputs, assumptions and
 * limitations — without leaving the page.
 */
export function CalcDisclosure({
  calculation,
  label = "How this is calculated",
  className,
}: {
  calculation: Pick<Calculation, "method" | "as_of" | "assumptions" | "limitations" | "inputs" | "source">;
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className={cn("text-xs", className)}>
      <button
        onClick={() => setOpen((current) => !current)}
        className="inline-flex items-center gap-1 font-medium text-ink-muted transition-colors hover:text-primary"
        aria-expanded={open}
      >
        <Info className="size-3.5" aria-hidden />
        {label}
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} aria-hidden />
      </button>

      {open ? (
        <div className="mt-3 animate-slide-up space-y-3 rounded-md border border-border bg-surface-muted/60 p-4 leading-relaxed">
          <div>
            <p className="section-label">Method</p>
            <p className="mt-1 text-ink">{calculation.method}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <p className="section-label">As of</p>
              <p className="mt-1 tabular text-ink">{formatDate(calculation.as_of, "long")}</p>
            </div>
            <div>
              <p className="section-label">Source</p>
              <p className="mt-1 text-ink">{titleCase(calculation.source)}</p>
            </div>
          </div>

          {calculation.inputs && Object.keys(calculation.inputs).length > 0 ? (
            <div>
              <p className="section-label">Inputs</p>
              <dl className="mt-1.5 grid gap-x-6 gap-y-1 sm:grid-cols-2">
                {Object.entries(calculation.inputs)
                  .slice(0, 8)
                  .map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-3 border-b border-border/60 py-0.5">
                      <dt className="text-ink-muted">{titleCase(key)}</dt>
                      <dd className="tabular text-ink">{formatInput(value)}</dd>
                    </div>
                  ))}
              </dl>
            </div>
          ) : null}

          {calculation.assumptions?.length ? (
            <div>
              <p className="section-label">Assumptions</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-ink-muted">
                {calculation.assumptions.map((assumption) => (
                  <li key={assumption}>{assumption}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {calculation.limitations?.length ? (
            <div>
              <p className="section-label">Limitations</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-ink-muted">
                {calculation.limitations.map((limitation) => (
                  <li key={limitation}>{limitation}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function formatInput(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    if (Math.abs(value) > 0 && Math.abs(value) < 1) return formatPercent(value);
    return Math.abs(value) >= 1000 ? formatCurrency(value, { compact: true }) : String(value);
  }
  if (Array.isArray(value)) return value.slice(0, 4).join(", ");
  return String(value);
}

/* ---------------------------------------------------------- Projection note */

export function ProjectionNotice({ className }: { className?: string }) {
  return (
    <p className={cn("flex items-start gap-2 text-xs leading-relaxed text-ink-muted", className)}>
      <Info className="mt-0.5 size-3.5 shrink-0 text-ink-subtle" aria-hidden />
      <span>
        Projections are illustrative, not guaranteed. They assume a constant rate of return and uninterrupted
        contributions; real markets vary and the order of returns matters.
      </span>
    </p>
  );
}
