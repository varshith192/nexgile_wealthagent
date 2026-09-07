"use client";

/**
 * Loading, empty, error and permission states (§45).
 *
 * No screen in this product is ever allowed to be blank. `DataState` wraps a
 * fetch result and guarantees the user sees something useful in every case.
 */

import Link from "next/link";
import { AlertTriangle, FileQuestion, Inbox, Lock, RefreshCw, SearchX, ShieldAlert } from "lucide-react";

import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Button, Card, Skeleton } from "@/components/ui";

export function LoadingCard({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <Card className={cn("p-5", className)}>
      <Skeleton className="h-3 w-28" />
      <Skeleton className="mt-4 h-7 w-44" />
      <div className="mt-5 space-y-2.5">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton key={index} className={index % 2 ? "h-3 w-3/5" : "h-3 w-4/5"} />
        ))}
      </div>
    </Card>
  );
}

export function LoadingGrid({ count = 4, columns = 4 }: { count?: number; columns?: number }) {
  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${columns >= 4 ? 220 : 300}px, 1fr))` }}
    >
      {Array.from({ length: count }).map((_, index) => (
        <LoadingCard key={index} lines={2} />
      ))}
    </div>
  );
}

export function LoadingTable({ rows = 6 }: { rows?: number }) {
  return (
    <Card>
      <div className="border-b border-border px-5 py-4">
        <Skeleton className="h-4 w-40" />
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="flex items-center gap-4 px-5 py-3.5">
            <Skeleton className="h-3 w-1/4" />
            <Skeleton className="h-3 w-1/6" />
            <Skeleton className="ml-auto h-3 w-20" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
    </Card>
  );
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      <div className="flex size-11 items-center justify-center rounded-full bg-surface-muted">
        <Icon className="size-5 text-ink-subtle" />
      </div>
      <p className="mt-4 text-sm font-medium text-ink">{title}</p>
      {description ? <p className="mt-1 max-w-sm text-sm leading-6 text-ink-muted">{description}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function NoResults({ query, onClear }: { query?: string; onClear?: () => void }) {
  return (
    <EmptyState
      icon={SearchX}
      title={query ? `No matches for “${query}”` : "No matches"}
      description="Try a different term, or clear the filters to see everything."
      action={
        onClear ? (
          <Button size="sm" onClick={onClear}>
            Clear filters
          </Button>
        ) : undefined
      }
    />
  );
}

export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const apiError = error instanceof ApiError ? error : null;
  const status = apiError?.status ?? 500;

  if (status === 403) {
    return (
      <EmptyState
        icon={Lock}
        title="You do not have access to this"
        description={apiError?.message ?? "Your role does not include this workspace. Contact your administrator if you need it."}
        className={className}
        action={
          <Button size="sm" onClick={() => window.history.back()}>
            Go back
          </Button>
        }
      />
    );
  }

  if (status === 401) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Your session has ended"
        description="Sign in again to continue."
        className={className}
        action={
          <Link href="/login">
            <Button size="sm" variant="primary">
              Sign in
            </Button>
          </Link>
        }
      />
    );
  }

  if (status === 404) {
    return (
      <EmptyState
        icon={FileQuestion}
        title="Not found"
        description={apiError?.message ?? "That record does not exist, or it has been removed."}
        className={className}
      />
    );
  }

  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      <div className="flex size-11 items-center justify-center rounded-full bg-negative-soft">
        <AlertTriangle className="size-5 text-negative" />
      </div>
      <p className="mt-4 text-sm font-medium text-ink">{apiError?.title ?? "Something went wrong"}</p>
      <p className="mt-1 max-w-md text-sm leading-6 text-ink-muted">
        {apiError?.message ?? "We could not load this view. Please try again."}
      </p>
      {onRetry ? (
        <Button size="sm" variant="secondary" className="mt-5" onClick={onRetry}>
          <RefreshCw />
          Try again
        </Button>
      ) : null}
    </div>
  );
}

/**
 * The one wrapper every data-backed panel uses.
 *
 * It renders exactly one of: loading, error, empty, or the content — so a
 * screen can never fall through to nothing.
 */
export function DataState<T>({
  loading,
  error,
  data,
  onRetry,
  loadingFallback,
  emptyWhen,
  empty,
  children,
}: {
  loading: boolean;
  error: unknown;
  data: T | null | undefined;
  onRetry?: () => void;
  loadingFallback?: React.ReactNode;
  emptyWhen?: (data: T) => boolean;
  empty?: React.ReactNode;
  children: (data: T) => React.ReactNode;
}) {
  if (loading && !data) return <>{loadingFallback ?? <LoadingCard />}</>;
  if (error && !data) return <ErrorState error={error} onRetry={onRetry} />;
  if (!data) return <>{empty ?? <EmptyState title="Nothing to show yet" />}</>;
  if (emptyWhen?.(data)) return <>{empty ?? <EmptyState title="Nothing to show yet" />}</>;
  return <>{children(data)}</>;
}
