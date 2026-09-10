"use client";

/**
 * The single sign-in surface (§6).
 *
 * One credential path serves all ten roles; the server decides where each one
 * lands. The demo panel is clearly labelled as demo data — no production
 * credential appears anywhere on this page.
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BadgeCheck,
  ChevronRight,
  Info,
  Loader2,
  LockKeyhole,
  Radar,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DEMO_PASSWORD, type DemoAccount } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, Field, Input } from "@/components/ui";
import { Logo } from "@/components/layout/logo";

const DEMO_ACCOUNTS: DemoAccount[] = [
  { label: "Client Demo", email: "priya.sharma@example.com", role: "client", role_label: "Client", full_name: "Priya Sharma", title: null, home_route: "/dashboard" },
  { label: "Advisor Demo", email: "arjun.mehta@nexgile.example", role: "advisor", role_label: "Advisor", full_name: "Arjun Mehta", title: "Senior Wealth Advisor", home_route: "/advisor" },
  { label: "Sponsor Demo", email: "deepa.krishnan@brightpath.example", role: "plan_sponsor", role_label: "Plan Sponsor", full_name: "Deepa Krishnan", title: "VP Human Resources", home_route: "/institutional" },
  { label: "Participant Demo", email: "nikhil.verma@brightpath.example", role: "participant", role_label: "Participant", full_name: "Nikhil Verma", title: "Senior Engineer", home_route: "/participant" },
  { label: "Compliance Demo", email: "neha.kapoor@nexgile.example", role: "compliance", role_label: "Compliance", full_name: "Neha Kapoor", title: "Head of Compliance", home_route: "/compliance" },
  { label: "Admin Demo", email: "suresh.pillai@nexgile.example", role: "admin", role_label: "Admin", full_name: "Suresh Pillai", title: "Managing Director", home_route: "/admin" },
];

export default function LoginPage() {
  const router = useRouter();
  const { signIn, status, user } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoAccounts] = useState<DemoAccount[]>(DEMO_ACCOUNTS);
  const [showForgot, setShowForgot] = useState(false);

  useEffect(() => {
    if (status === "authenticated" && user) router.replace(user.home_route);
  }, [status, user, router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const profile = await signIn(email.trim(), password, rememberMe);
      router.replace(profile.home_route);
    } catch (caught) {
      const message =
        caught instanceof ApiError
          ? caught.status === 0
            ? "Could not reach the Nexgile API. Confirm the backend is running and NEXT_PUBLIC_API_URL is set."
            : caught.message
          : "Sign-in failed. Please try again.";
      setError(message);
      setSubmitting(false);
    }
  };

  const signInAs = async (account: DemoAccount) => {
    setEmail(account.email);
    setPassword(DEMO_PASSWORD);
    setError(null);
    setSubmitting(true);
    try {
      const profile = await signIn(account.email, DEMO_PASSWORD, true);
      router.replace(profile.home_route);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Sign-in failed.");
      setSubmitting(false);
    }
  };

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_minmax(0,520px)]">
      {/* ------------------------------------------------------ Brand panel */}
      <section className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-10 text-sidebar-foreground lg:flex xl:p-14">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "linear-gradient(hsl(var(--sidebar-foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--sidebar-foreground)) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
          }}
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -right-32 -top-32 size-[28rem] rounded-full bg-primary/12 blur-3xl"
          aria-hidden
        />

        <div className="relative flex items-center gap-3">
          <Logo size={34} />
          <span className="text-lg font-semibold tracking-tight text-white">
            Nexgile <span className="font-medium text-sidebar-muted">WealthAgent</span>
          </span>
        </div>

        <div className="relative max-w-lg">
          <p className="text-2xs font-semibold uppercase tracking-[0.16em] text-primary">
            Unified wealth management
          </p>
          <h1 className="mt-4 text-[2.5rem] font-semibold leading-[1.12] tracking-tight text-white xl:text-[2.875rem]">
            Every account, goal and decision in one place.
          </h1>
          <p className="mt-5 text-base leading-7 text-sidebar-foreground/75">
            Portfolios, goals, tax, estate and philanthropy — one platform, one audit trail.
          </p>

          <ul className="mt-9 space-y-4">
            {[
              {
                icon: TrendingUp,
                title: "Verified figures, always",
                body: "Every number shows its method, date and assumptions.",
              },
              {
                icon: Radar,
                title: "WealthAgent intelligence",
                body: "Insights grounded in your own data — never invented.",
              },
              {
                icon: BadgeCheck,
                title: "Controlled workflows",
                body: "Every recommendation moves through review and approval.",
              },
            ].map((feature) => (
              <li key={feature.title} className="flex gap-3.5">
                <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/15">
                  <feature.icon className="size-4 text-primary" aria-hidden />
                </span>
                <span>
                  <span className="block text-sm font-medium text-white">{feature.title}</span>
                  <span className="mt-0.5 block text-sm leading-6 text-sidebar-foreground/65">{feature.body}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-sidebar-muted">
          Demonstration environment · fictional households and fictional financial data
        </p>
      </section>

      {/* ------------------------------------------------------- Sign-in form */}
      <section className="flex flex-col justify-center bg-background px-5 py-10 sm:px-10 lg:px-12">
        <div className="mx-auto w-full max-w-md">
          <div className="flex items-center gap-2.5 lg:hidden">
            <Logo size={30} />
            <span className="text-base font-semibold tracking-tight text-ink">
              Nexgile <span className="font-medium text-ink-muted">WealthAgent</span>
            </span>
          </div>

          <div className="mt-8 lg:mt-0">
            <h2 className="text-2xl font-semibold tracking-tight text-ink">Sign in</h2>
            <p className="mt-1.5 text-sm text-ink-muted">
              Use your Nexgile credentials. Your role determines the workspace you land in.
            </p>
          </div>

          <form onSubmit={submit} className="mt-7 space-y-4" noValidate>
            <Field label="Email address">
              <Input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                aria-invalid={Boolean(error)}
              />
            </Field>

            <Field label="Password">
              <Input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                aria-invalid={Boolean(error)}
              />
            </Field>

            <div className="flex items-center justify-between gap-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-muted">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                  className="size-4 rounded border-input text-primary focus-visible:ring-ring"
                />
                Remember me
              </label>
              <button
                type="button"
                onClick={() => setShowForgot((value) => !value)}
                className="text-sm font-medium text-primary hover:underline"
              >
                Forgot password?
              </button>
            </div>

            {showForgot ? (
              <div className="flex gap-2 rounded-md border border-info/25 bg-info-soft px-3 py-2.5 text-xs leading-relaxed text-ink-muted">
                <Info className="mt-0.5 size-3.5 shrink-0 text-info" aria-hidden />
                <span>
                  Password resets are handled by your firm&rsquo;s identity provider. In this demonstration
                  environment, use one of the labelled demo accounts below.
                </span>
              </div>
            ) : null}

            {error ? (
              <div
                role="alert"
                className="rounded-md border border-negative/25 bg-negative-soft px-3 py-2.5 text-sm text-negative"
              >
                {error}
              </div>
            ) : null}

            <Button type="submit" variant="primary" size="lg" className="w-full" loading={submitting}>
              {submitting ? "Signing in…" : "Sign in"}
              {!submitting ? <ArrowRight /> : null}
            </Button>
          </form>

          {/* ------------------------------------------------ Demo accounts */}
          {demoAccounts.length > 0 ? (
            <Card className="mt-8 overflow-hidden">
              <div className="flex items-center justify-between gap-3 border-b border-border bg-surface-muted/70 px-4 py-3">
                <div>
                  <p className="text-sm font-semibold text-ink">Demo accounts</p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    One click signs you in as that role. Fictional data only.
                  </p>
                </div>
                <Badge tone="primary">Evaluation</Badge>
              </div>

              <ul className="divide-y divide-border">
                {demoAccounts.map((account) => (
                  <li key={account.email}>
                    <button
                      onClick={() => signInAs(account)}
                      disabled={submitting}
                      className={cn(
                        "flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left transition-colors",
                        "hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60",
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-ink">{account.label}</span>
                        <span className="block truncate text-xs text-ink-muted">
                          {account.full_name}
                          {account.title ? ` · ${account.title}` : ""}
                        </span>
                        <span className="block truncate font-mono text-xs text-ink-subtle">{account.email}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2">
                        <Badge tone="outline">{account.home_route}</Badge>
                        {submitting ? (
                          <Loader2 className="size-3.5 animate-spin text-ink-subtle" aria-hidden />
                        ) : (
                          <ChevronRight className="size-4 text-ink-subtle" aria-hidden />
                        )}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>

              <div className="flex items-start gap-2 border-t border-border bg-surface-muted/50 px-4 py-2.5 text-xs text-ink-muted">
                <LockKeyhole className="mt-0.5 size-3.5 shrink-0 text-ink-subtle" aria-hidden />
                <span>
                  Demo password <code className="rounded bg-surface px-1 py-0.5 font-mono text-ink">{DEMO_PASSWORD}</code>.
                  These are demonstration identities. No production credential is stored or displayed here.
                </span>
              </div>
            </Card>
          ) : null}

          <p className="mt-6 flex items-start gap-2 text-xs leading-relaxed text-ink-subtle">
            <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span>
              Access is authorised server side on every request. Sign-in attempts, successful or not, are written
              to the audit trail.
            </span>
          </p>
        </div>
      </section>
    </main>
  );
}
