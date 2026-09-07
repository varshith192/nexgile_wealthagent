"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { isActivePath, navigationFor } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui";
import { Logo, Wordmark } from "@/components/layout/logo";

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { user } = useAuth();
  const sections = navigationFor(user?.role);

  return (
    <>
      {open ? (
        <div className="fixed inset-0 z-30 animate-fade-in bg-ink/40 lg:hidden" onClick={onClose} aria-hidden />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-200 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-sidebar-border px-4">
          <Link href={user?.home_route ?? "/dashboard"} className="flex items-center gap-2.5 min-w-0">
            <Logo size={26} />
            <Wordmark className="truncate text-[0.9375rem] text-sidebar-foreground" subdued />
          </Link>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onClose}
            className="text-sidebar-muted hover:bg-sidebar-active hover:text-sidebar-foreground lg:hidden"
            aria-label="Close navigation"
          >
            <X />
          </Button>
        </div>

        <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5" aria-label="Main navigation">
          {sections.map((section) => (
            <div key={section.title}>
              <p className="px-2.5 pb-2 text-2xs font-semibold uppercase tracking-[0.1em] text-sidebar-muted">
                {section.title}
              </p>
              <ul className="space-y-0.5">
                {section.items.map((item) => {
                  const active = isActivePath(pathname, item);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onClose}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors",
                          active
                            ? "bg-sidebar-active font-medium text-white"
                            : "text-sidebar-foreground/80 hover:bg-sidebar-active/60 hover:text-white",
                        )}
                      >
                        <Icon
                          className={cn(
                            "size-4 shrink-0 transition-colors",
                            active ? "text-primary" : "text-sidebar-muted group-hover:text-sidebar-foreground",
                          )}
                          aria-hidden
                        />
                        <span className="truncate">{item.label}</span>
                        {active ? (
                          <span className="ml-auto h-4 w-0.5 rounded-full bg-primary" aria-hidden />
                        ) : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="shrink-0 border-t border-sidebar-border px-4 py-3.5">
          <p className="text-2xs leading-relaxed text-sidebar-muted">
            Figures come from the platform&rsquo;s calculation engine. WealthAgent explains them; it does not
            produce them.
          </p>
        </div>
      </aside>
    </>
  );
}
