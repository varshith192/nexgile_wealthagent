"use client";

/** Advisor task queue with SLA and overdue tracking. */

import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckSquare } from "lucide-react";

import { api } from "@/lib/api";
import { formatDate, titleCase } from "@/lib/format";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardHeader, Select, TD, TH, THead, TR, Table, Tabs } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type Task = {
  id: string;
  title: string;
  description: string | null;
  category: string;
  priority: string;
  status: string;
  due_date: string | null;
  is_overdue: boolean;
  household: string;
  household_id: string | null;
  assignee: string;
  sla_days: number | null;
};

const STATUSES = ["open", "in_progress", "blocked", "complete"];

export default function AdvisorTasksPage() {
  const { data, error, loading, refetch } = useApi<Task[]>("/api/advisor/tasks");
  const [tab, setTab] = useState("open");

  const { run: update, pending } = useMutation(async (taskId: string, status: string) => {
    const result = await api.patch(`/api/advisor/tasks/${taskId}`, { status });
    refetch();
    return result;
  });

  const visible = useMemo(() => {
    if (!data) return [];
    if (tab === "all") return data;
    if (tab === "overdue") return data.filter((task) => task.is_overdue);
    return data.filter((task) => task.status === tab);
  }, [data, tab]);

  return (
    <div className="space-y-6">
      <PageHeader title="Tasks" description="Service and planning work across your book, with due dates and service levels." />

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Open" value={String(data.filter((task) => task.status === "open").length)} icon={CheckSquare} tone="primary" />
          <StatTile label="In progress" value={String(data.filter((task) => task.status === "in_progress").length)} />
          <StatTile
            label="Overdue"
            value={String(data.filter((task) => task.is_overdue).length)}
            tone={data.some((task) => task.is_overdue) ? "negative" : "positive"}
            icon={AlertTriangle}
          />
          <StatTile label="Completed" value={String(data.filter((task) => task.status === "complete").length)} tone="positive" />
        </StatRow>
      ) : null}

      <Card>
        <div className="px-5 pt-4">
          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[
              { value: "open", label: "Open" },
              { value: "in_progress", label: "In progress" },
              { value: "overdue", label: "Overdue" },
              { value: "complete", label: "Complete" },
              { value: "all", label: "All" },
            ]}
          />
        </div>

        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={6} />}
          emptyWhen={() => visible.length === 0}
          empty={<EmptyState icon={CheckSquare} title="Nothing in this view" description="Tasks appear here as they are raised." />}
        >
          {() => (
            <Table>
              <THead>
                <TR>
                  <TH>Task</TH>
                  <TH>Household</TH>
                  <TH>Category</TH>
                  <TH>Priority</TH>
                  <TH>Due</TH>
                  <TH>Assignee</TH>
                  <TH align="right">Status</TH>
                </TR>
              </THead>
              <tbody>
                {visible.map((task) => (
                  <TR key={task.id}>
                    <TD>
                      <span className={cn("font-medium", task.is_overdue ? "text-negative" : "text-ink")}>{task.title}</span>
                      {task.description ? (
                        <span className="mt-0.5 block max-w-[22rem] truncate text-xs text-ink-muted">{task.description}</span>
                      ) : null}
                    </TD>
                    <TD className="text-xs">
                      {task.household_id ? (
                        <Link href={`/advisor/clients/${task.household_id}`} className="text-ink hover:text-primary">
                          {task.household}
                        </Link>
                      ) : (
                        task.household
                      )}
                    </TD>
                    <TD><Badge tone="outline" size="sm">{titleCase(task.category)}</Badge></TD>
                    <TD>
                      <Badge tone={task.priority === "high" ? "warning" : "outline"} size="sm">
                        {titleCase(task.priority)}
                      </Badge>
                    </TD>
                    <TD className="whitespace-nowrap text-xs">
                      <span className={task.is_overdue ? "font-medium text-negative" : "text-ink-muted"}>
                        {task.due_date ? formatDate(task.due_date) : "—"}
                      </span>
                      {task.sla_days ? <span className="mt-0.5 block text-2xs text-ink-subtle">{task.sla_days}-day SLA</span> : null}
                    </TD>
                    <TD className="text-xs text-ink-muted">{task.assignee}</TD>
                    <TD align="right">
                      <Select
                        value={task.status}
                        disabled={pending}
                        onChange={(event) => update(task.id, event.target.value)}
                        className="h-7 w-32 text-2xs"
                        aria-label={`Status for ${task.title}`}
                      >
                        {STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {titleCase(status)}
                          </option>
                        ))}
                      </Select>
                    </TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          )}
        </DataState>
      </Card>
    </div>
  );
}
