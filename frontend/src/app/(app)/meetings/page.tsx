"use client";

/** Meetings (§27): upcoming, past, agendas, notes and action items. */

import { CalendarDays, CheckCircle2, Circle, MapPin, Users } from "lucide-react";

import { api } from "@/lib/api";
import { formatDate, formatDateTime, formatRelative, titleCase } from "@/lib/format";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { PageHeader, Section } from "@/components/shared/page";
import { DataState, EmptyState, LoadingGrid } from "@/components/shared/states";

type Meeting = {
  id: string;
  title: string;
  meeting_type: string;
  starts_at: string;
  duration_minutes: number;
  location: string;
  status: string;
  agenda: string[];
  notes: string | null;
  summary: string | null;
  attendees: string[];
  advisor: string | null;
  action_items: { id: string; title: string; owner: string; status: string; due_date: string | null; notes: string | null }[];
};

type MeetingsPayload = { upcoming: Meeting[]; past: Meeting[]; next_meeting: Meeting | null };

export default function MeetingsPage() {
  const { data, error, loading, refetch } = useApi<MeetingsPayload>("/api/meetings");

  const { run: complete, pending } = useMutation(async (itemId: string) => {
    await api.post(`/api/meetings/action-items/${itemId}/complete`);
    refetch();
    return true;
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Meetings" description="Scheduled reviews, past discussions and the actions that came out of them." />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingGrid count={2} columns={2} />}>
        {(payload) => (
          <>
            {payload.next_meeting ? (
              <Card className="border-primary/25 bg-primary-soft/30">
                <CardBody className="flex flex-wrap items-start justify-between gap-6 py-5">
                  <div className="min-w-0">
                    <Badge tone="primary">Next meeting</Badge>
                    <h2 className="mt-2.5 text-lg font-semibold text-ink">{payload.next_meeting.title}</h2>
                    <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-muted">
                      <span className="flex items-center gap-1.5">
                        <CalendarDays className="size-3.5" aria-hidden />
                        {formatDateTime(payload.next_meeting.starts_at)} ({formatRelative(payload.next_meeting.starts_at)})
                      </span>
                      <span className="flex items-center gap-1.5">
                        <MapPin className="size-3.5" aria-hidden />
                        {payload.next_meeting.location}
                      </span>
                      <span>{payload.next_meeting.duration_minutes} minutes</span>
                    </p>
                    {payload.next_meeting.attendees.length > 0 ? (
                      <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-muted">
                        <Users className="size-3.5" aria-hidden />
                        {payload.next_meeting.attendees.join(" · ")}
                      </p>
                    ) : null}
                  </div>

                  {payload.next_meeting.agenda.length > 0 ? (
                    <div className="min-w-[16rem] max-w-md flex-1">
                      <p className="section-label">Agenda</p>
                      <ol className="mt-2 space-y-1.5">
                        {payload.next_meeting.agenda.map((item, index) => (
                          <li key={item} className="flex gap-2.5 text-sm text-ink-muted">
                            <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-primary/15 text-[0.5625rem] font-semibold text-primary">
                              {index + 1}
                            </span>
                            {item}
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </CardBody>
              </Card>
            ) : null}

            <Section title="Upcoming" description={`${payload.upcoming.length} scheduled`}>
              {payload.upcoming.length === 0 ? (
                <Card>
                  <EmptyState icon={CalendarDays} title="Nothing scheduled" description="Your advisor will schedule the next review." />
                </Card>
              ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                  {payload.upcoming.map((meeting) => (
                    <MeetingCard key={meeting.id} meeting={meeting} onComplete={complete} pending={pending} />
                  ))}
                </div>
              )}
            </Section>

            <Section title="Previous meetings" description={`${payload.past.length} on record`}>
              {payload.past.length === 0 ? (
                <Card>
                  <EmptyState title="No past meetings" />
                </Card>
              ) : (
                <div className="grid gap-4 lg:grid-cols-2">
                  {payload.past.map((meeting) => (
                    <MeetingCard key={meeting.id} meeting={meeting} onComplete={complete} pending={pending} />
                  ))}
                </div>
              )}
            </Section>
          </>
        )}
      </DataState>
    </div>
  );
}

function MeetingCard({
  meeting,
  onComplete,
  pending,
}: {
  meeting: Meeting;
  onComplete: (id: string) => void;
  pending: boolean;
}) {
  return (
    <Card>
      <CardHeader
        title={meeting.title}
        description={`${formatDateTime(meeting.starts_at)} · ${meeting.location}`}
        action={<StatusBadge status={meeting.status} />}
      />
      <CardBody className="space-y-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="outline">{titleCase(meeting.meeting_type)}</Badge>
          <Badge tone="outline">{meeting.duration_minutes} min</Badge>
          {meeting.advisor ? <Badge tone="outline">{meeting.advisor}</Badge> : null}
        </div>

        {meeting.agenda.length > 0 ? (
          <div>
            <p className="section-label">Agenda</p>
            <ul className="mt-1.5 space-y-1">
              {meeting.agenda.map((item) => (
                <li key={item} className="flex gap-2 text-xs leading-5 text-ink-muted">
                  <span className="mt-1.5 size-1 shrink-0 rounded-full bg-ink-subtle" aria-hidden />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {meeting.summary ? (
          <div>
            <p className="section-label">Summary</p>
            <p className="mt-1 text-sm leading-6 text-ink-muted">{meeting.summary}</p>
          </div>
        ) : null}

        {meeting.notes ? (
          <div>
            <p className="section-label">Notes</p>
            <p className="mt-1 text-sm leading-6 text-ink-muted">{meeting.notes}</p>
          </div>
        ) : null}

        {meeting.action_items.length > 0 ? (
          <div>
            <p className="section-label">Action items</p>
            <ul className="mt-2 space-y-2">
              {meeting.action_items.map((item) => {
                const done = item.status === "complete";
                return (
                  <li key={item.id} className="flex items-start justify-between gap-3 rounded-md border border-border px-3 py-2.5">
                    <div className="flex min-w-0 gap-2.5">
                      {done ? (
                        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-positive" aria-hidden />
                      ) : (
                        <Circle className="mt-0.5 size-4 shrink-0 text-ink-subtle" aria-hidden />
                      )}
                      <div className="min-w-0">
                        <p className={cn("text-sm leading-5", done ? "text-ink-muted line-through" : "text-ink")}>{item.title}</p>
                        <p className="mt-0.5 text-2xs text-ink-subtle">
                          {item.owner}
                          {item.due_date ? ` · due ${formatDate(item.due_date)}` : ""}
                        </p>
                      </div>
                    </div>
                    {!done ? (
                      <Button size="sm" variant="ghost" loading={pending} onClick={() => onComplete(item.id)}>
                        Mark done
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}
