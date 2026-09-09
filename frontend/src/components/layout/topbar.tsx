"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, Check, ChevronDown, LockKeyhole, LogOut, Menu, Moon, RefreshCw, Sun, UserRound } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatRelative } from "@/lib/format";
import { DEMO_PASSWORD, type DemoAccount, type Notification } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge, Button } from "@/components/ui";
import { SeverityBadge } from "@/components/shared/indicators";
import { GlobalSearch } from "@/components/layout/global-search";

export function Topbar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-surface/85 px-4 backdrop-blur-md lg:px-6">
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onOpenSidebar}
        className="lg:hidden"
        aria-label="Open navigation"
      >
        <Menu />
      </Button>

      <div className="flex-1">
        <GlobalSearch />
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <ThemeToggle />
        <NotificationCenter />
        <UserMenu />
      </div>
    </header>
  );
}

/* ------------------------------------------------------------ Theme toggle */

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem("nexgile.theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const next = stored ? stored === "dark" : prefersDark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem("nexgile.theme", next ? "dark" : "light");
  };

  return (
    <Button variant="ghost" size="icon-sm" onClick={toggle} aria-label={dark ? "Use light theme" : "Use dark theme"}>
      {dark ? <Sun /> : <Moon />}
    </Button>
  );
}

/* ------------------------------------------------------ Notification centre */

function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const panelRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .get<{ notifications: Notification[]; unread_count: number }>("/api/notifications?limit=12")
      .then((payload) => {
        setItems(payload.notifications);
        setUnread(payload.unread_count);
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useOutsideClick(panelRef, () => setOpen(false));

  const markAll = async () => {
    await api.post("/api/notifications/read-all").catch(() => null);
    load();
  };

  const markOne = async (id: string) => {
    await api.post(`/api/notifications/${id}/read`).catch(() => null);
    setItems((current) => current.map((row) => (row.id === id ? { ...row, is_read: true } : row)));
    setUnread((count) => Math.max(count - 1, 0));
  };

  return (
    <div className="relative" ref={panelRef}>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => setOpen((value) => !value)}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        aria-expanded={open}
      >
        <Bell />
        {unread > 0 ? (
          <span className="absolute right-1 top-1 flex size-4 items-center justify-center rounded-full bg-negative text-[0.5625rem] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </Button>

      {open ? (
        <div className="absolute right-0 top-full z-30 mt-2 w-[22rem] animate-slide-up overflow-hidden rounded-lg border border-border bg-surface shadow-pop">
          <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
            <p className="text-sm font-semibold text-ink">Notifications</p>
            {unread > 0 ? (
              <button onClick={markAll} className="text-xs font-medium text-primary hover:underline">
                Mark all read
              </button>
            ) : null}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <p className="px-4 py-8 text-center text-sm text-ink-muted">Loading…</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-8 text-center text-sm text-ink-muted">You are all caught up.</p>
            ) : (
              <ul className="divide-y divide-border">
                {items.map((item) => (
                  <li key={item.id} className={cn("px-4 py-3", !item.is_read && "bg-primary-soft/40")}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <SeverityBadge severity={item.severity} />
                          <Badge tone="outline" size="sm">
                            {item.category_label}
                          </Badge>
                        </div>
                        <p className="mt-1.5 text-sm font-medium leading-5 text-ink">{item.title}</p>
                        <p className="mt-0.5 text-xs leading-5 text-ink-muted">{item.body}</p>
                        <div className="mt-1.5 flex items-center gap-3">
                          <span className="text-2xs text-ink-subtle">{formatRelative(item.created_at)}</span>
                          {item.action_url ? (
                            <Link
                              href={item.action_url}
                              onClick={() => setOpen(false)}
                              className="text-2xs font-medium text-primary hover:underline"
                            >
                              View
                            </Link>
                          ) : null}
                        </div>
                      </div>
                      {!item.is_read ? (
                        <button
                          onClick={() => markOne(item.id)}
                          className="shrink-0 rounded p-1 text-ink-subtle transition-colors hover:bg-surface-muted hover:text-primary"
                          aria-label="Mark as read"
                        >
                          <Check className="size-3.5" />
                        </button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ---------------------------------------------------------------- Account */

function UserMenu() {
  const router = useRouter();
  const { user, signIn, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [demoAccounts, setDemoAccounts] = useState<DemoAccount[]>([]);
  const [switching, setSwitching] = useState<string | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  useOutsideClick(menuRef, () => setOpen(false));

  useEffect(() => {
    api
      .get<DemoAccount[]>("/api/auth/demo-accounts")
      .then(setDemoAccounts)
      .catch(() => setDemoAccounts([]));
  }, []);

  if (!user) return null;

  const otherAccounts = demoAccounts.filter((account) => account.email !== user.email);

  const switchTo = async (account: DemoAccount) => {
    setSwitchError(null);
    setSwitching(account.email);
    try {
      const profile = await signIn(account.email, DEMO_PASSWORD, true);
      setOpen(false);
      router.push(profile.home_route);
    } catch (caught) {
      setSwitchError(caught instanceof ApiError ? caught.message : "Could not switch accounts.");
    } finally {
      setSwitching(null);
    }
  };

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex items-center gap-2 rounded-md py-1 pl-1 pr-1.5 transition-colors hover:bg-surface-muted"
      >
        <span className="flex size-7 items-center justify-center rounded-full bg-primary text-2xs font-semibold text-primary-foreground">
          {user.avatar_initials}
        </span>
        <span className="hidden text-left sm:block">
          <span className="block text-xs font-medium leading-4 text-ink">{user.full_name}</span>
          <span className="block text-2xs leading-4 text-ink-muted">{user.role_label}</span>
        </span>
        <ChevronDown className="size-3.5 text-ink-subtle" aria-hidden />
      </button>

      {open ? (
        <div className="absolute right-0 top-full z-30 mt-2 w-72 animate-slide-up overflow-hidden rounded-lg border border-border bg-surface shadow-pop">
          <div className="border-b border-border px-4 py-3">
            <p className="text-sm font-semibold text-ink">{user.full_name}</p>
            <p className="truncate text-xs text-ink-muted">{user.email}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone="primary">{user.role_label}</Badge>
              {user.is_demo ? <Badge tone="outline">Demo</Badge> : null}
            </div>
          </div>

          <div className="px-4 py-2.5 text-xs text-ink-muted">
            <p className="flex items-center justify-between gap-2">
              <span>Permissions</span>
              <span className="font-medium tabular text-ink">{user.permissions.length}</span>
            </p>
            <p className="mt-1 flex items-center justify-between gap-2">
              <span>Time zone</span>
              <span className="text-ink">{user.timezone}</span>
            </p>
          </div>

          <div className="border-t border-border p-1.5">
            <Link
              href={user.home_route}
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-md px-2.5 py-2 text-sm text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink"
            >
              <UserRound className="size-4" />
              My workspace
            </Link>
            <button
              onClick={signOut}
              className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-ink-muted transition-colors hover:bg-negative-soft hover:text-negative"
            >
              <LogOut className="size-4" />
              Sign out
            </button>
          </div>

          {otherAccounts.length > 0 ? (
            <div className="border-t border-border">
              <p className="px-4 pt-2.5 text-2xs font-semibold uppercase tracking-wide text-ink-subtle">
                Switch demo account
              </p>
              {switchError ? <p className="px-4 pt-1 text-xs text-negative">{switchError}</p> : null}
              <ul className="max-h-64 overflow-y-auto p-1.5">
                {otherAccounts.map((account) => (
                  <li key={account.email}>
                    <button
                      onClick={() => switchTo(account)}
                      disabled={switching !== null}
                      className="flex w-full items-center justify-between gap-2 rounded-md px-2.5 py-2 text-left text-sm text-ink-muted transition-colors hover:bg-surface-muted hover:text-ink disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-ink">{account.label}</span>
                        <span className="block truncate text-2xs text-ink-subtle">{account.email}</span>
                      </span>
                      {switching === account.email ? (
                        <RefreshCw className="size-3.5 shrink-0 animate-spin text-ink-subtle" aria-hidden />
                      ) : (
                        <Badge tone="outline" size="sm">
                          {account.role_label}
                        </Badge>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
              <p className="flex items-start gap-1.5 border-t border-border bg-surface-muted/50 px-4 py-2 text-2xs text-ink-muted">
                <LockKeyhole className="mt-0.5 size-3 shrink-0 text-ink-subtle" aria-hidden />
                <span>
                  Demo password <code className="rounded bg-surface px-1 py-0.5 font-mono text-ink">{DEMO_PASSWORD}</code> for every account.
                </span>
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function useOutsideClick(ref: React.RefObject<HTMLElement | null>, handler: () => void) {
  useEffect(() => {
    const listener = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) handler();
    };
    document.addEventListener("mousedown", listener);
    return () => document.removeEventListener("mousedown", listener);
  }, [ref, handler]);
}
