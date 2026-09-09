"use client";

/**
 * WealthAgent (§19).
 *
 * Three surfaces — what changed, what to consider, what to do next — plus a
 * conversational panel. Everything on this page is derived from figures the
 * calculation engine produced, and every insight shows its own working.
 */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ChevronRight,
  CircleHelp,
  Cpu,
  Info,
  Lightbulb,
  ListChecks,
  Send,
  ShieldCheck,
} from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCurrency, formatDate, formatPercent, titleCase } from "@/lib/format";
import type { Insight, NextAction, Recommendation, RecommendationDraft, SupportingFact } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Input, Tabs } from "@/components/ui";
import { SeverityBadge, StatusBadge } from "@/components/shared/indicators";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type WorkspacePayload = {
  as_of: string;
  household: { id: string; name: string };
  provider: { name: string; mode: string; model: string | null; description: string; capabilities: string[]; requires_api_key: boolean; is_configured: boolean };
  insights: Insight[];
  recommendation_drafts: RecommendationDraft[];
  actions: NextAction[];
  recommendations: Recommendation[];
  summary: { insight_count: number; high_severity: number; draft_count: number; open_recommendations: number };
  data_freshness: Record<string, string>;
  disclaimer: string;
};

type AgentAnswer = {
  answer: string;
  intent: string;
  grounded_facts: SupportingFact[];
  related_routes: NextAction[];
  followups: string[];
  confidence: number;
  source: string;
  disclaimer: string;
};

export default function WealthAgentPage() {
  const { can } = useAuth();
  const { data, error, loading, refetch } = useApi<WorkspacePayload>("/api/wealthagent");
  const [tab, setTab] = useState("insights");

  return (
    <div className="space-y-6">
      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={4} />}>
        {(workspace) => (
          <>
            <PageHeader
              title="WealthAgent"
              description="What changed in your finances, what to consider, and what you can do about it — each traced back to the figure that produced it."
              meta={
                <>
                  <Badge tone="primary">
                    <Cpu className="size-3" />
                    {workspace.provider.mode === "mock" ? "Deterministic rules engine" : titleCase(workspace.provider.name)}
                  </Badge>
                  <span className="text-xs text-ink-muted">As of {formatDate(workspace.as_of)}</span>
                </>
              }
            />

            <StatRow columns={4}>
              <StatTile label="Insights" value={String(workspace.summary.insight_count)} icon={Lightbulb} tone="primary" hint="Rules that fired against your data" />
              <StatTile
                label="Needs attention"
                value={String(workspace.summary.high_severity)}
                tone={workspace.summary.high_severity ? "warning" : "positive"}
                hint="High or critical severity"
              />
              <StatTile label="Suggested recommendations" value={String(workspace.summary.draft_count)} icon={ListChecks} hint="Drafts awaiting a decision" />
              <StatTile
                label="In review"
                value={String(workspace.summary.open_recommendations)}
                hint="Tracked recommendations not yet resolved"
              />
            </StatRow>

            {/* ---------------------------------------- Provenance banner */}
            <Card className="border-primary/20 bg-primary-soft/40">
              <CardBody className="flex flex-wrap items-start gap-3 py-4">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink">How WealthAgent works</p>
                  <p className="mt-1 text-xs leading-relaxed text-ink-muted">{workspace.provider.description}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-ink-muted">{workspace.disclaimer}</p>
                </div>
                <Badge tone="outline">
                  {workspace.provider.requires_api_key
                    ? workspace.provider.is_configured
                      ? "API key configured"
                      : "No API key — using rules engine"
                    : "No API key required"}
                </Badge>
              </CardBody>
            </Card>

            <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
              <div className="space-y-6">
                <Card>
                  <div className="px-5 pt-4">
                    <Tabs
                      value={tab}
                      onChange={setTab}
                      tabs={[
                        { value: "insights", label: "Insights", count: workspace.insights.length },
                        { value: "recommendations", label: "Recommendations", count: workspace.recommendation_drafts.length },
                        { value: "actions", label: "Actions", count: workspace.actions.length },
                        { value: "tracked", label: "Tracked", count: workspace.recommendations.length },
                      ]}
                    />
                  </div>

                  <CardBody>
                    {tab === "insights" ? <InsightList insights={workspace.insights} /> : null}
                    {tab === "recommendations" ? (
                      <DraftList
                        drafts={workspace.recommendation_drafts}
                        householdId={workspace.household.id}
                        canCreate={can("recommendations:create")}
                        onCreated={refetch}
                      />
                    ) : null}
                    {tab === "actions" ? <ActionList actions={workspace.actions} /> : null}
                    {tab === "tracked" ? <TrackedList recommendations={workspace.recommendations} /> : null}
                  </CardBody>
                </Card>
              </div>

              <AskPanel householdId={workspace.household.id} />
            </div>
          </>
        )}
      </DataState>
    </div>
  );
}

/* ------------------------------------------------------------- Insights */

function InsightList({ insights }: { insights: Insight[] }) {
  const [expanded, setExpanded] = useState<string | null>(insights[0]?.key ?? null);

  if (insights.length === 0) {
    return (
      <EmptyState
        icon={Lightbulb}
        title="Nothing crossed a threshold"
        description="No portfolio, goal, tax, estate or document rule fired against your current data."
      />
    );
  }

  return (
    <ul className="space-y-3">
      {insights.map((insight) => {
        const open = expanded === insight.key;
        return (
          <li key={insight.key}>
            <div
              className={cn(
                "rounded-lg border transition-colors",
                open ? "border-primary/30 bg-primary-soft/25" : "border-border bg-surface",
              )}
            >
              <button
                onClick={() => setExpanded(open ? null : insight.key)}
                className="flex w-full items-start justify-between gap-3 px-4 py-3.5 text-left"
                aria-expanded={open}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={insight.severity} />
                    <Badge tone="outline" size="sm">
                      {titleCase(insight.category)}
                    </Badge>
                    <span className="text-2xs text-ink-subtle">
                      confidence {formatPercent(insight.confidence, { decimals: 0 })}
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-ink">{insight.title}</p>
                  <p className="mt-1 text-sm leading-6 text-ink-muted">{insight.summary}</p>
                </div>
                <ChevronRight className={cn("mt-1 size-4 shrink-0 text-ink-subtle transition-transform", open && "rotate-90")} aria-hidden />
              </button>

              {open ? (
                <div className="animate-slide-up space-y-4 border-t border-border px-4 py-4">
                  <Block label="Impact">{insight.impact}</Block>
                  <Block label="Suggested next step">{insight.suggested_next_step}</Block>

                  {insight.supporting_facts.length > 0 ? (
                    <div>
                      <p className="section-label">Supporting data</p>
                      <dl className="mt-2 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
                        {insight.supporting_facts.map((fact) => (
                          <div key={`${fact.label}-${fact.value}`} className="flex items-baseline justify-between gap-3 border-b border-border/60 py-1">
                            <dt className="text-xs text-ink-muted">{fact.label}</dt>
                            <dd className="text-xs font-medium tabular text-ink">{fact.value}</dd>
                          </div>
                        ))}
                      </dl>
                      <p className="mt-2 text-2xs text-ink-subtle">
                        Source: {titleCase(insight.supporting_facts[0]?.source ?? "calculation engine")}
                        {insight.as_of ? ` · as of ${formatDate(insight.as_of)}` : ""}
                      </p>
                    </div>
                  ) : null}

                  {insight.calculation_method ? <Block label="Calculation">{insight.calculation_method}</Block> : null}

                  {insight.assumptions.length > 0 ? (
                    <div>
                      <p className="section-label">Assumptions</p>
                      <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-muted">
                        {insight.assumptions.map((assumption) => (
                          <li key={assumption}>{assumption}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {insight.limitations.length > 0 ? (
                    <div>
                      <p className="section-label">Limitations</p>
                      <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-muted">
                        {insight.limitations.map((limitation) => (
                          <li key={limitation}>{limitation}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {insight.action_url ? (
                    <Link href={insight.action_url}>
                      <Button size="sm" variant="primary">
                        Open {titleCase(insight.category)}
                        <ArrowRight />
                      </Button>
                    </Link>
                  ) : null}
                </div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="section-label">{label}</p>
      <p className="mt-1 text-sm leading-6 text-ink-muted">{children}</p>
    </div>
  );
}

/* ------------------------------------------------------------ Drafts */

function DraftList({
  drafts,
  householdId,
  canCreate,
  onCreated,
}: {
  drafts: RecommendationDraft[];
  householdId: string;
  canCreate: boolean;
  onCreated: () => void;
}) {
  const [created, setCreated] = useState<string[]>([]);
  const { run, pending, message } = useMutation(async (draftKey: string) => {
    const result = await api.post("/api/recommendations/from-draft", {
      draft_key: draftKey,
      household_id: householdId,
      submit: true,
    });
    setCreated((current) => [...current, draftKey]);
    onCreated();
    return result;
  });

  if (drafts.length === 0) {
    return <EmptyState icon={ListChecks} title="No recommendations right now" description="Nothing in your data warrants a proposal today." />;
  }

  return (
    <div className="space-y-3">
      {message ? (
        <p role="alert" className="rounded-md border border-negative/25 bg-negative-soft px-3 py-2 text-sm text-negative">
          {message}
        </p>
      ) : null}

      {drafts.map((draft) => (
        <div key={draft.key} className="rounded-lg border border-border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={draft.severity} />
                <Badge tone="outline" size="sm">{titleCase(draft.category)}</Badge>
                <Badge tone="warning" size="sm">Requires approval</Badge>
              </div>
              <p className="mt-2 text-sm font-semibold text-ink">{draft.title}</p>
              <p className="mt-1 text-sm leading-6 text-ink-muted">{draft.summary}</p>
            </div>
            {draft.impact_amount !== null ? (
              <div className="shrink-0 text-right">
                <p className="section-label">{draft.impact_label ?? "Estimated impact"}</p>
                <p className="mt-1 text-lg font-semibold tabular text-ink">
                  {formatCurrency(draft.impact_amount, { compact: true })}
                </p>
              </div>
            ) : null}
          </div>

          <div className="mt-4 grid gap-4 border-t border-border pt-3 sm:grid-cols-2">
            <Block label="Why">{draft.rationale}</Block>
            <Block label="Suggested action">{draft.suggested_action}</Block>
          </div>

          {draft.limitations.length > 0 ? (
            <ul className="mt-3 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-subtle">
              {draft.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          ) : null}

          {canCreate ? (
            <div className="mt-4 flex items-center gap-3">
              {created.includes(draft.key) ? (
                <Badge tone="positive">Submitted for review</Badge>
              ) : (
                <Button size="sm" variant="primary" loading={pending} onClick={() => run(draft.key)}>
                  Submit for approval
                  <ArrowRight />
                </Button>
              )}
              <span className="text-xs text-ink-subtle">Routes to an advisor before anything happens.</span>
            </div>
          ) : (
            <p className="mt-4 text-xs text-ink-subtle">
              Discuss this with your advisor — they can raise it for review from the advisor workstation.
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------ Actions */

function ActionList({ actions }: { actions: NextAction[] }) {
  if (actions.length === 0) {
    return <EmptyState title="No next steps" description="Nothing is waiting on you right now." />;
  }

  return (
    <ul className="space-y-2">
      {actions.map((action) => (
        <li key={action.key}>
          <Link
            href={action.route}
            className="flex items-center justify-between gap-4 rounded-lg border border-border px-4 py-3.5 transition-colors hover:border-primary/30 hover:bg-primary-soft/30"
          >
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                {action.label}
                {action.requires_approval ? <Badge tone="warning" size="sm">Needs approval</Badge> : null}
              </p>
              <p className="mt-0.5 text-xs leading-5 text-ink-muted">{action.description}</p>
            </div>
            <ArrowRight className="size-4 shrink-0 text-ink-subtle" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------ Tracked */

function TrackedList({ recommendations }: { recommendations: Recommendation[] }) {
  if (recommendations.length === 0) {
    return <EmptyState title="No tracked recommendations" description="Recommendations raised for review will appear here." />;
  }

  return (
    <ul className="divide-y divide-border">
      {recommendations.map((recommendation) => (
        <li key={recommendation.id} className="py-3.5 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={recommendation.status} />
                <SeverityBadge severity={recommendation.severity} />
                <Badge tone="outline" size="sm">{titleCase(recommendation.category)}</Badge>
              </div>
              <p className="mt-2 text-sm font-medium text-ink">{recommendation.title}</p>
              <p className="mt-0.5 text-xs leading-5 text-ink-muted">{recommendation.summary}</p>
              <p className="mt-1.5 text-2xs text-ink-subtle">
                Raised {formatDate(recommendation.created_at)} · generated by {recommendation.generator} rules
              </p>
            </div>
            {recommendation.impact_amount !== null ? (
              <div className="shrink-0 text-right">
                <p className="text-sm font-semibold tabular text-ink">
                  {formatCurrency(recommendation.impact_amount, { compact: true })}
                </p>
                <p className="text-2xs text-ink-subtle">{recommendation.impact_label}</p>
              </div>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ---------------------------------------------------------- Ask panel */

const STARTERS = [
  "What is my net worth?",
  "How is my portfolio performing this year?",
  "Am I too concentrated in any one holding?",
  "Am I on track for retirement?",
  "Are there tax opportunities available?",
];

type Turn = { role: "user" | "agent"; text: string; answer?: AgentAnswer };

function AskPanel({ householdId }: { householdId: string }) {
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { run, pending } = useMutation(async (text: string) => {
    const answer = await api.post<AgentAnswer>("/api/wealthagent/ask", {
      question: text,
      household_id: householdId,
    });
    setTurns((current) => [...current, { role: "agent", text: answer.answer, answer }]);
    return answer;
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, pending]);

  const ask = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || pending) return;
    setTurns((current) => [...current, { role: "user", text: trimmed }]);
    setQuestion("");
    await run(trimmed);
  };

  return (
    <Card className="flex h-full flex-col xl:sticky xl:top-20 xl:max-h-[calc(100vh-6rem)]">
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <CircleHelp className="size-4 text-primary" aria-hidden />
            Ask WealthAgent
          </span>
        }
        description="Answers are grounded in your own verified figures."
      />

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {turns.length === 0 ? (
          <div className="space-y-4">
            <p className="text-sm leading-6 text-ink-muted">
              Ask about your net worth, performance, allocation, goals, tax, estate or giving. Every answer quotes the
              figure it came from.
            </p>
            <div>
              <p className="section-label">Try asking</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {STARTERS.map((starter) => (
                  <button
                    key={starter}
                    onClick={() => ask(starter)}
                    className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-left text-xs text-ink-muted transition-colors hover:border-primary/30 hover:bg-primary-soft hover:text-primary"
                  >
                    {starter}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          turns.map((turn, index) =>
            turn.role === "user" ? (
              <div key={index} className="flex justify-end">
                <p className="max-w-[85%] rounded-lg rounded-br-sm bg-primary px-3.5 py-2 text-sm leading-6 text-primary-foreground">
                  {turn.text}
                </p>
              </div>
            ) : (
              <div key={index} className="space-y-2.5">
                <div className="rounded-lg rounded-bl-sm border border-border bg-surface-muted/70 px-3.5 py-2.5">
                  <p className="text-sm leading-6 text-ink">{turn.text}</p>
                </div>

                {turn.answer?.grounded_facts.length ? (
                  <div className="rounded-md border border-border px-3 py-2.5">
                    <p className="section-label">Figures quoted</p>
                    <dl className="mt-1.5 space-y-1">
                      {turn.answer.grounded_facts.map((fact) => (
                        <div key={`${fact.label}-${fact.value}`} className="flex items-baseline justify-between gap-3">
                          <dt className="text-xs text-ink-muted">{fact.label}</dt>
                          <dd className="text-xs font-medium tabular text-ink">{fact.value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ) : null}

                {turn.answer?.related_routes.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {turn.answer.related_routes.map((route) => (
                      <Link key={route.key} href={route.route}>
                        <Button size="sm" variant="subtle">
                          {route.label}
                          <ChevronRight />
                        </Button>
                      </Link>
                    ))}
                  </div>
                ) : null}

                {turn.answer?.followups.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {turn.answer.followups.map((followup) => (
                      <button
                        key={followup}
                        onClick={() => ask(followup)}
                        className="rounded-md border border-border px-2 py-1 text-2xs text-ink-muted transition-colors hover:border-primary/30 hover:text-primary"
                      >
                        {followup}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ),
          )
        )}

        {pending ? (
          <div className="flex gap-1.5 rounded-lg border border-border bg-surface-muted/70 px-3.5 py-3">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="size-1.5 animate-pulse rounded-full bg-ink-subtle"
                style={{ animationDelay: `${dot * 140}ms` }}
              />
            ))}
          </div>
        ) : null}
      </div>

      <div className="border-t border-border p-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            ask(question);
          }}
          className="flex items-center gap-2"
        >
          <Input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask WealthAgent…"
            aria-label="Ask WealthAgent a question"
            disabled={pending}
          />
          <Button type="submit" variant="primary" size="icon" loading={pending} aria-label="Send question">
            {pending ? null : <Send />}
          </Button>
        </form>
        <p className="mt-2 flex items-start gap-1.5 text-2xs leading-relaxed text-ink-subtle">
          <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
          Informational only. Not investment, tax or legal advice.
        </p>
      </div>
    </Card>
  );
}
