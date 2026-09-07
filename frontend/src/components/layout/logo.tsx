import { cn } from "@/lib/utils";

/** The Nexgile mark: an ascending set of bars enclosed by a rounded frame. */
export function Logo({ className, size = 32 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role="img"
      aria-label="Nexgile"
      className={cn("shrink-0", className)}
    >
      <rect x="1" y="1" width="30" height="30" rx="8" className="fill-primary" />
      <rect x="8" y="18" width="3.5" height="6.5" rx="1.4" fill="white" fillOpacity="0.55" />
      <rect x="14.25" y="13" width="3.5" height="11.5" rx="1.4" fill="white" fillOpacity="0.78" />
      <rect x="20.5" y="7.5" width="3.5" height="17" rx="1.4" fill="white" />
    </svg>
  );
}

export function Wordmark({ className, subdued = false }: { className?: string; subdued?: boolean }) {
  return (
    <span className={cn("flex items-baseline gap-1.5 font-semibold tracking-tight", className)}>
      <span>Nexgile</span>
      <span className={cn("text-sm font-medium", subdued ? "text-sidebar-muted" : "text-ink-muted")}>
        WealthAgent
      </span>
    </span>
  );
}
