"use client";

/** Page chrome and metric tiles shared by every workspace. */

import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui";
import { Delta } from "@/components/shared/indicators";

export function PageHeader({
  title,
  description,
  actions,
  meta,
  breadcrumb,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  breadcrumb?: { label: string; href?: string }[];
  className?: string;
}) {
  return (
    <div className={cn("space-y-4", className)}>
      {breadcrumb?.length ? (
        <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-ink-muted">
          {breadcrumb.map((crumb, index) => (
            <span key={`${crumb.label}-${index}`} className="flex items-center gap-1.5">
              {index > 0 ? <ChevronRight className="size-3 text-ink-subtle" aria-hidden /> : null}
              {crumb.href ? (
                <Link href={crumb.href} className="transition-colors hover:text-primary">
                  {crumb.label}
                </Link>
              ) : (
                <span className="text-ink">{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
      ) : null}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
          {description ? <p className="mt-1 max-w-3xl text-sm leading-6 text-ink-muted">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>

      {meta ? <div className="flex flex-wrap items-center gap-x-3 gap-y-2">{meta}</div> : null}
    </div>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-4", className)}>
      {title || actions ? (
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            {title ? <h2 className="text-base font-semibold tracking-tight text-ink">{title}</h2> : null}
            {description ? <p className="mt-0.5 text-sm text-ink-muted">{description}</p> : null}
          </div>
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function StatTile({
  label,
  value,
  delta,
  deltaPercent,
  hint,
  icon: Icon,
  tone = "default",
  href,
  footer,
  className,
}: {
  label: string;
  value: string;
  delta?: number | null;
  deltaPercent?: number | null;
  hint?: string;
  icon?: LucideIcon;
  tone?: "default" | "primary" | "positive" | "warning" | "negative";
  href?: string;
  footer?: React.ReactNode;
  className?: string;
}) {
  const accent = {
    default: "text-ink-subtle",
    primary: "text-primary",
    positive: "text-positive",
    warning: "text-warning",
    negative: "text-negative",
  }[tone];

  const content = (
    <Card
      className={cn(
        "flex h-full flex-col p-5 transition-shadow",
        href && "hover:shadow-raised",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="section-label">{label}</p>
        {Icon ? <Icon className={cn("size-4 shrink-0", accent)} aria-hidden /> : null}
      </div>

      <p className="mt-3 text-2xl font-semibold tabular tracking-tight text-ink">{value}</p>

      {delta !== undefined || deltaPercent !== undefined ? (
        <div className="mt-1.5">
          <Delta value={delta ?? undefined} percent={deltaPercent ?? undefined} />
        </div>
      ) : null}

      {hint ? <p className="mt-1.5 text-xs leading-5 text-ink-muted">{hint}</p> : null}
      {footer ? <div className="mt-auto pt-4">{footer}</div> : null}
    </Card>
  );

  return href ? (
    <Link href={href} className="block h-full">
      {content}
    </Link>
  ) : (
    content
  );
}

export function StatRow({ children, columns = 4 }: { children: React.ReactNode; columns?: 2 | 3 | 4 | 5 }) {
  const columnClass = {
    2: "sm:grid-cols-2",
    3: "sm:grid-cols-2 lg:grid-cols-3",
    4: "sm:grid-cols-2 xl:grid-cols-4",
    5: "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5",
  }[columns];

  return <div className={cn("grid gap-4", columnClass)}>{children}</div>;
}

export function KeyValue({
  items,
  columns = 2,
  className,
}: {
  items: { label: string; value: React.ReactNode; hint?: string }[];
  columns?: 1 | 2 | 3;
  className?: string;
}) {
  const columnClass = { 1: "", 2: "sm:grid-cols-2", 3: "sm:grid-cols-3" }[columns];
  return (
    <dl className={cn("grid gap-x-8 gap-y-3", columnClass, className)}>
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline justify-between gap-4 border-b border-border/60 pb-2">
          <dt className="text-xs text-ink-muted">{item.label}</dt>
          <dd className="text-right text-sm font-medium tabular text-ink">
            {item.value}
            {item.hint ? <span className="mt-0.5 block text-xs font-normal text-ink-subtle">{item.hint}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}
