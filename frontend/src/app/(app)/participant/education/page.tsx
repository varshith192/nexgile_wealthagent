"use client";

/** Financial education (§35): learning paths, guides, videos and progress. */

import { useState } from "react";
import { BookOpen, CircleCheck, Clock, GraduationCap, PlayCircle, Video } from "lucide-react";

import { formatDate, formatPercent, titleCase } from "@/lib/format";
import type { ParticipantPortal } from "@/lib/participant";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Card, CardBody, CardHeader, Progress, Tabs } from "@/components/ui";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

const TYPE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  guide: BookOpen,
  video: Video,
  webinar: PlayCircle,
};

export default function EducationPage() {
  const { data, error, loading, refetch } = useApi<ParticipantPortal>("/api/participant");
  const [path, setPath] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <PageHeader title="Education" description="Short, practical material on how your plan works and how to use it well." />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={3} columns={3} />}>
        {(portal) => {
          const education = portal.education;
          const visible = path === "all" ? education.items : education.items.filter((item) => item.learning_path === path);
          const completed = education.items.filter((item) => item.status === "complete").length;

          return (
            <>
              <StatRow columns={4}>
                <StatTile label="Modules" value={String(education.items.length)} icon={GraduationCap} tone="primary" />
                <StatTile label="Completed" value={String(completed)} tone="positive" icon={CircleCheck} />
                <StatTile label="Overall progress" value={formatPercent(education.completion_rate, { decimals: 0 })} />
                <StatTile
                  label="Time to finish"
                  value={`${education.items.filter((item) => item.status !== "complete").reduce((total, item) => total + item.duration_minutes, 0)} min`}
                  hint="Remaining material"
                  icon={Clock}
                />
              </StatRow>

              <Card>
                <CardHeader title="Learning paths" description="Your progress through each track." />
                <CardBody className="space-y-4">
                  {education.paths.map((entry) => (
                    <div key={entry.learning_path}>
                      <div className="flex items-baseline justify-between text-sm">
                        <span className="font-medium text-ink">{entry.learning_path}</span>
                        <span className="tabular text-xs text-ink-muted">
                          {entry.completed} of {entry.total} complete
                        </span>
                      </div>
                      <Progress
                        value={entry.progress}
                        tone={entry.progress >= 1 ? "positive" : entry.progress > 0 ? "primary" : "warning"}
                        className="mt-1.5"
                        showTrackLabel
                      />
                    </div>
                  ))}
                </CardBody>
              </Card>

              <Card>
                <div className="px-5 pt-4">
                  <Tabs
                    value={path}
                    onChange={setPath}
                    tabs={[
                      { value: "all", label: "All", count: education.items.length },
                      ...education.paths.map((entry) => ({
                        value: entry.learning_path,
                        label: entry.learning_path,
                        count: entry.total,
                      })),
                    ]}
                  />
                </div>

                <CardBody>
                  {visible.length === 0 ? (
                    <EmptyState icon={GraduationCap} title="No material in this path" />
                  ) : (
                    <ul className="grid gap-4 lg:grid-cols-2">
                      {visible.map((item) => {
                        const Icon = TYPE_ICON[item.content_type] ?? BookOpen;
                        const open = selected === item.id;
                        return (
                          <li key={item.id}>
                            <div
                              className={cn(
                                "h-full rounded-lg border p-4 transition-colors",
                                item.status === "complete" ? "border-positive/25 bg-positive-soft/20" : "border-border",
                              )}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex min-w-0 gap-3">
                                  <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-surface-muted">
                                    <Icon className="size-4 text-ink-subtle" />
                                  </span>
                                  <div className="min-w-0">
                                    <p className="text-sm font-semibold leading-5 text-ink">{item.title}</p>
                                    <p className="mt-1 flex flex-wrap items-center gap-1.5 text-2xs text-ink-subtle">
                                      <Badge tone="outline" size="sm">{titleCase(item.content_type)}</Badge>
                                      <Badge tone="outline" size="sm">{titleCase(item.level)}</Badge>
                                      <span>{item.duration_minutes} min</span>
                                    </p>
                                  </div>
                                </div>
                                {item.status === "complete" ? (
                                  <Badge tone="positive" size="sm">
                                    <CircleCheck className="size-3" />
                                    Done
                                  </Badge>
                                ) : item.status === "in_progress" ? (
                                  <Badge tone="warning" size="sm">In progress</Badge>
                                ) : null}
                              </div>

                              <p className="mt-3 text-sm leading-6 text-ink-muted">{item.summary}</p>

                              {item.progress_percent > 0 && item.progress_percent < 1 ? (
                                <Progress value={item.progress_percent} tone="primary" className="mt-3" showTrackLabel />
                              ) : null}

                              {item.body ? (
                                <>
                                  <button
                                    onClick={() => setSelected(open ? null : item.id)}
                                    className="mt-3 text-xs font-medium text-primary hover:underline"
                                    aria-expanded={open}
                                  >
                                    {open ? "Show less" : "Read more"}
                                  </button>
                                  {open ? (
                                    <p className="mt-2 animate-slide-up border-t border-border pt-3 text-sm leading-6 text-ink-muted">
                                      {item.body}
                                    </p>
                                  ) : null}
                                </>
                              ) : null}

                              {item.completed_at ? (
                                <p className="mt-3 text-2xs text-ink-subtle">
                                  Completed {formatDate(item.completed_at)}
                                  {item.score !== null ? ` · scored ${formatPercent(item.score, { decimals: 0 })}` : ""}
                                </p>
                              ) : null}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </CardBody>
              </Card>
            </>
          );
        }}
      </DataState>
    </div>
  );
}
