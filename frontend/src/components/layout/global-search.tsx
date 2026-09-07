"use client";

/** Global search (§36): typeahead across every entity the caller may see. */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock, CornerDownLeft, Loader2, Search, Star, X } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Badge, Button, Input } from "@/components/ui";

type SearchResult = { id: string; title: string; subtitle: string; route: string };
type SearchGroup = { category: string; label: string; count: number; results: SearchResult[] };
type SearchPayload = { query: string; groups: SearchGroup[]; total: number; message?: string };
type Suggestions = {
  recent: { query: string; result_count: number }[];
  suggested: string[];
  saved_views: { id: string; name: string; query: string }[];
};

export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchPayload | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const flat = results?.groups.flatMap((group) => group.results) ?? [];

  // Cmd/Ctrl+K opens search from anywhere.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
      }
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    inputRef.current?.focus();
    if (!suggestions) {
      api.get<Suggestions>("/api/search/suggestions").then(setSuggestions).catch(() => setSuggestions(null));
    }
  }, [open, suggestions]);

  useEffect(() => {
    if (!open) return;
    if (query.trim().length < 2) {
      setResults(null);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      api
        .get<SearchPayload>(`/api/search?q=${encodeURIComponent(query.trim())}`, controller.signal)
        .then((payload) => {
          setResults(payload);
          setActiveIndex(0);
        })
        .catch(() => setResults(null))
        .finally(() => setLoading(false));
    }, 220);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, open]);

  const go = useCallback(
    (route: string) => {
      setOpen(false);
      setQuery("");
      setResults(null);
      router.push(route);
    },
    [router],
  );

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, flat.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && flat[activeIndex]) {
      event.preventDefault();
      go(flat[activeIndex].route);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-border bg-surface-muted px-3 text-sm text-ink-subtle transition-colors hover:border-input hover:bg-surface"
      >
        <Search className="size-4 shrink-0" aria-hidden />
        <span className="truncate">Search clients, accounts, holdings, documents…</span>
        <kbd className="ml-auto hidden shrink-0 rounded border border-border bg-surface px-1.5 py-0.5 text-2xs font-medium text-ink-subtle sm:block">
          ⌘K
        </kbd>
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[10vh]">
          <div className="absolute inset-0 animate-fade-in bg-ink/35 backdrop-blur-[2px]" onClick={() => setOpen(false)} aria-hidden />

          <div
            role="dialog"
            aria-modal="true"
            aria-label="Global search"
            className="relative flex max-h-[70vh] w-full max-w-2xl animate-slide-up flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-pop"
          >
            <div className="flex items-center gap-2 border-b border-border px-4">
              <Search className="size-4 shrink-0 text-ink-subtle" aria-hidden />
              <Input
                ref={inputRef}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Search across clients, accounts, holdings, goals, documents…"
                className="h-12 border-0 bg-transparent px-0 shadow-none focus-visible:border-0"
              />
              {loading ? <Loader2 className="size-4 animate-spin text-ink-subtle" aria-hidden /> : null}
              <Button variant="ghost" size="icon-sm" onClick={() => setOpen(false)} aria-label="Close search">
                <X />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto p-2">
              {query.trim().length < 2 ? (
                <SuggestionPanel suggestions={suggestions} onPick={setQuery} />
              ) : results && results.total > 0 ? (
                <div className="space-y-3">
                  {results.groups.map((group) => (
                    <div key={group.category}>
                      <p className="px-2 pb-1 pt-2 text-2xs font-semibold uppercase tracking-[0.08em] text-ink-subtle">
                        {group.label}
                        <span className="ml-1.5 font-normal normal-case tracking-normal">({group.count})</span>
                      </p>
                      <ul>
                        {group.results.map((result) => {
                          const index = flat.findIndex((row) => row.id === result.id && row.route === result.route);
                          return (
                            <li key={`${group.category}-${result.id}`}>
                              <button
                                onMouseEnter={() => setActiveIndex(index)}
                                onClick={() => go(result.route)}
                                className={cn(
                                  "flex w-full items-center justify-between gap-3 rounded-md px-2.5 py-2 text-left transition-colors",
                                  index === activeIndex ? "bg-primary-soft" : "hover:bg-surface-muted",
                                )}
                              >
                                <span className="min-w-0">
                                  <span className="block truncate text-sm font-medium text-ink">{result.title}</span>
                                  <span className="block truncate text-xs text-ink-muted">{result.subtitle}</span>
                                </span>
                                {index === activeIndex ? (
                                  <CornerDownLeft className="size-3.5 shrink-0 text-primary" aria-hidden />
                                ) : null}
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-4 py-10 text-center">
                  <p className="text-sm font-medium text-ink">No matches for “{query}”</p>
                  <p className="mt-1 text-xs text-ink-muted">
                    {results?.message ?? "Try a client name, ticker, account or document title."}
                  </p>
                </div>
              )}
            </div>

            <div className="flex items-center gap-3 border-t border-border bg-surface-muted/60 px-4 py-2 text-2xs text-ink-subtle">
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-border bg-surface px-1">↑</kbd>
                <kbd className="rounded border border-border bg-surface px-1">↓</kbd> navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-border bg-surface px-1">↵</kbd> open
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border border-border bg-surface px-1">esc</kbd> close
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function SuggestionPanel({
  suggestions,
  onPick,
}: {
  suggestions: Suggestions | null;
  onPick: (query: string) => void;
}) {
  if (!suggestions) {
    return <p className="px-4 py-10 text-center text-sm text-ink-muted">Type at least two characters to search.</p>;
  }

  return (
    <div className="space-y-4 p-2">
      {suggestions.saved_views.length ? (
        <Group title="Saved views" icon={Star}>
          {suggestions.saved_views.map((view) => (
            <Chip key={view.id} onClick={() => onPick(view.query)}>
              {view.name}
            </Chip>
          ))}
        </Group>
      ) : null}

      {suggestions.recent.length ? (
        <Group title="Recent searches" icon={Clock}>
          {suggestions.recent.slice(0, 6).map((entry) => (
            <Chip key={entry.query} onClick={() => onPick(entry.query)}>
              {entry.query}
              <Badge tone="outline" size="sm" className="ml-1.5">
                {entry.result_count}
              </Badge>
            </Chip>
          ))}
        </Group>
      ) : null}

      <Group title="Suggested for you" icon={Search}>
        {suggestions.suggested.map((entry) => (
          <Chip key={entry} onClick={() => onPick(entry)}>
            {entry}
          </Chip>
        ))}
      </Group>
    </div>
  );
}

function Group({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="flex items-center gap-1.5 px-2 pb-2 text-2xs font-semibold uppercase tracking-[0.08em] text-ink-subtle">
        <Icon className="size-3" />
        {title}
      </p>
      <div className="flex flex-wrap gap-1.5 px-2">{children}</div>
    </div>
  );
}

function Chip({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center rounded-md border border-border bg-surface px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-primary/30 hover:bg-primary-soft hover:text-primary"
    >
      {children}
    </button>
  );
}
