"use client";

/** Goals (§14): every goal with its projection, plus goal creation. */

import { useState } from "react";
import Link from "next/link";
import { ChevronRight, Plus, Target } from "lucide-react";

import { api } from "@/lib/api";
import { formatCurrency, formatDate, formatPercent } from "@/lib/format";
import type { Calculation, GoalRow } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { Badge, Button, Card, Dialog, Field, Input, Progress, Select } from "@/components/ui";
import { CalcDisclosure, GoalStatusBadge, ProjectionNotice } from "@/components/shared/indicators";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type GoalsPayload = Calculation<{
  goals: GoalRow[];
  total_target: number;
  total_current: number;
  overall_progress: number;
  goals_off_track: number;
  goal_count: number;
}>;

const GOAL_TYPES = [
  { value: "retirement", label: "Retirement" },
  { value: "education", label: "Education" },
  { value: "home", label: "Home" },
  { value: "legacy", label: "Legacy" },
  { value: "life_event", label: "Life event" },
  { value: "custom", label: "Custom" },
];

export default function GoalsPage() {
  const { data, error, loading, refetch } = useApi<GoalsPayload>("/api/goals");
  const [creating, setCreating] = useState(false);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Goals"
        description="What your money is for, how far along it is, and what the plan projects."
        actions={
          <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
            <Plus />
            New goal
          </Button>
        }
      />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={3} columns={3} />}>
        {(payload) => {
          const summary = payload.result;
          return (
            <>
              <StatRow columns={4}>
                <StatTile label="Goals tracked" value={String(summary.goal_count)} icon={Target} />
                <StatTile label="Total target" value={formatCurrency(summary.total_target, { compact: true })} />
                <StatTile
                  label="Currently funded"
                  value={formatCurrency(summary.total_current, { compact: true })}
                  hint={`${formatPercent(summary.overall_progress, { decimals: 0 })} of target`}
                  tone="primary"
                />
                <StatTile
                  label="Need attention"
                  value={String(summary.goals_off_track)}
                  hint={summary.goals_off_track ? "At risk or off track" : "All goals on plan"}
                  tone={summary.goals_off_track ? "warning" : "positive"}
                />
              </StatRow>

              {summary.goals.length === 0 ? (
                <Card>
                  <EmptyState
                    icon={Target}
                    title="No goals yet"
                    description="Add a goal to start tracking progress and comparing scenarios."
                    action={
                      <Button variant="primary" size="sm" onClick={() => setCreating(true)}>
                        <Plus />
                        Create your first goal
                      </Button>
                    }
                  />
                </Card>
              ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                  {summary.goals.map((goal) => {
                    const tone =
                      goal.status === "on_track"
                        ? "positive"
                        : goal.status === "off_track"
                          ? "negative"
                          : goal.status === "at_risk"
                            ? "warning"
                            : "primary";
                    return (
                      <Link key={goal.id} href={`/goals/${goal.id}`}>
                        <Card className="h-full p-5 transition-shadow hover:shadow-raised">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-base font-semibold text-ink">{goal.name}</p>
                              <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                                <Badge tone="outline" size="sm">
                                  {GOAL_TYPES.find((type) => type.value === goal.goal_type)?.label ?? goal.goal_type}
                                </Badge>
                                <span>Target {formatDate(goal.target_date)}</span>
                                <span>· {goal.years_to_target} years</span>
                                <Badge tone="outline" size="sm">{goal.priority} priority</Badge>
                              </p>
                            </div>
                            <GoalStatusBadge status={goal.status} />
                          </div>

                          <div className="mt-5">
                            <div className="flex items-baseline justify-between gap-3">
                              <span className="text-xl font-semibold tabular text-ink">
                                {formatCurrency(goal.current_amount, { compact: true })}
                              </span>
                              <span className="text-sm text-ink-muted">
                                of {formatCurrency(goal.target_amount, { compact: true })}
                              </span>
                            </div>
                            <Progress value={goal.progress_percent} tone={tone} className="mt-2.5" showTrackLabel />
                          </div>

                          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-2.5 border-t border-border pt-4 text-xs">
                            <Row label="Projected at target" value={formatCurrency(goal.projected_value, { compact: true })} />
                            <Row label="Inflation-adjusted target" value={formatCurrency(goal.inflation_adjusted_target, { compact: true })} />
                            <Row label="Funded ratio" value={formatPercent(goal.funded_ratio, { decimals: 0 })} />
                            <Row
                              label={goal.gap >= 0 ? "Projected surplus" : "Projected shortfall"}
                              value={formatCurrency(Math.abs(goal.gap), { compact: true })}
                              tone={goal.gap >= 0 ? "positive" : "negative"}
                            />
                          </dl>

                          {goal.additional_monthly_needed > 0 ? (
                            <p className="mt-4 rounded-md bg-warning-soft px-3 py-2 text-xs text-warning">
                              An additional {formatCurrency(goal.additional_monthly_needed)} a month closes the gap on
                              current assumptions.
                            </p>
                          ) : null}

                          <p className="mt-4 flex items-center gap-1 text-xs font-medium text-primary">
                            Compare scenarios <ChevronRight className="size-3.5" aria-hidden />
                          </p>
                        </Card>
                      </Link>
                    );
                  })}
                </div>
              )}

              <Card className="p-5">
                <ProjectionNotice />
                <CalcDisclosure calculation={payload} className="mt-3" />
              </Card>
            </>
          );
        }}
      </DataState>

      <CreateGoalDialog open={creating} onClose={() => setCreating(false)} onCreated={refetch} />
    </div>
  );
}

function Row({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "positive" | "negative" }) {
  const toneClass = { neutral: "text-ink", positive: "text-positive", negative: "text-negative" }[tone];
  return (
    <div>
      <dt className="text-ink-muted">{label}</dt>
      <dd className={`mt-0.5 font-medium tabular ${toneClass}`}>{value}</dd>
    </div>
  );
}

function CreateGoalDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    name: "",
    goal_type: "custom",
    target_amount: "",
    current_amount: "",
    target_date: "",
    monthly_contribution: "",
    expected_return: "0.06",
    priority: "medium",
  });

  const { run, pending, message, reset } = useMutation(async () =>
    api.post("/api/goals", {
      name: form.name.trim(),
      goal_type: form.goal_type,
      target_amount: Number(form.target_amount),
      current_amount: Number(form.current_amount || 0),
      target_date: form.target_date,
      monthly_contribution: Number(form.monthly_contribution || 0),
      expected_return: Number(form.expected_return),
      priority: form.priority,
    }),
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const created = await run();
    if (created) {
      onCreated();
      onClose();
      setForm({
        name: "",
        goal_type: "custom",
        target_amount: "",
        current_amount: "",
        target_date: "",
        monthly_contribution: "",
        expected_return: "0.06",
        priority: "medium",
      });
    }
  };

  const close = () => {
    reset();
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Create a goal"
      description="The projection updates as soon as the goal is saved."
      footer={
        <>
          <Button size="sm" onClick={close}>
            Cancel
          </Button>
          <Button size="sm" variant="primary" loading={pending} onClick={submit as unknown as () => void}>
            Create goal
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="Goal name">
          <Input
            required
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            placeholder="e.g. Sabbatical fund"
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Type">
            <Select value={form.goal_type} onChange={(event) => setForm({ ...form, goal_type: event.target.value })}>
              {GOAL_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Priority">
            <Select value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </Select>
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Target amount">
            <Input
              required
              type="number"
              min="1"
              step="1000"
              value={form.target_amount}
              onChange={(event) => setForm({ ...form, target_amount: event.target.value })}
              placeholder="250000"
            />
          </Field>
          <Field label="Amount already set aside">
            <Input
              type="number"
              min="0"
              step="1000"
              value={form.current_amount}
              onChange={(event) => setForm({ ...form, current_amount: event.target.value })}
              placeholder="40000"
            />
          </Field>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Target date">
            <Input
              required
              type="date"
              value={form.target_date}
              onChange={(event) => setForm({ ...form, target_date: event.target.value })}
            />
          </Field>
          <Field label="Monthly contribution">
            <Input
              type="number"
              min="0"
              step="100"
              value={form.monthly_contribution}
              onChange={(event) => setForm({ ...form, monthly_contribution: event.target.value })}
              placeholder="2000"
            />
          </Field>
        </div>

        <Field label="Expected annual return" hint="Used for the projection. 0.06 means 6% a year.">
          <Input
            type="number"
            step="0.005"
            min="-0.5"
            max="0.5"
            value={form.expected_return}
            onChange={(event) => setForm({ ...form, expected_return: event.target.value })}
          />
        </Field>

        {message ? (
          <p role="alert" className="rounded-md border border-negative/25 bg-negative-soft px-3 py-2 text-sm text-negative">
            {message}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
