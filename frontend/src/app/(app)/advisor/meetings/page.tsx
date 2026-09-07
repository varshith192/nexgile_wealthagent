"use client";

/** Advisor meeting calendar across the book. */

import Link from "next/link";
import { CalendarDays, MapPin, Users } from "lucide-react";

import { formatDateTime, formatRelative, titleCase } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import { Badge, Card, CardHeader } from "@/components/ui";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type AdvisorDashboard = {
  summary: { meetings_this_week: number };
  meetings: {
    id: string;
    title: string;
    household: string;
    household_id: string;
    starts_at: string;
    meeting_type: string;
    location: string;
  }[];
};

export default function AdvisorMeetingsPage() {
  const { data, error, loading, refetch } = useApi<AdvisorDashboard>("/api/advisor");

  return (
    <div className="space-y-6">
      <PageHeader title="Meetings" description="Scheduled reviews across every household in your book." />

      <DataState loading={loading} error={error} data={data} onRetry={refetch} loadingFallback={<LoadingTable rows={5} />}>
        {(dashboard) => (
          <>
            <StatRow columns={3}>
              <StatTile label="Scheduled" value={String(dashboard.meetings.length)} icon={CalendarDays} tone="primary" />
              <StatTile label="Within seven days" value={String(dashboard.summary.meetings_this_week)} tone="warning" />
              <StatTile
                label="Households with a meeting"
                value={String(new Set(dashboard.meetings.map((meeting) => meeting.household_id)).size)}
                icon={Users}
              />
            </StatRow>

            <Card>
              <CardHeader title="Upcoming" description="Ordered by start time." />
              {dashboard.meetings.length === 0 ? (
                <EmptyState icon={CalendarDays} title="Nothing scheduled" description="Meetings appear here once booked." />
              ) : (
                <ul className="divide-y divide-border">
                  {dashboard.meetings.map((meeting) => (
                    <li key={meeting.id} className="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-ink">{meeting.title}</p>
                        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                          <Link href={`/advisor/clients/${meeting.household_id}`} className="font-medium text-primary hover:underline">
                            {meeting.household}
                          </Link>
                          <span className="flex items-center gap-1">
                            <CalendarDays className="size-3" aria-hidden />
                            {formatDateTime(meeting.starts_at)}
                          </span>
                          <span className="flex items-center gap-1">
                            <MapPin className="size-3" aria-hidden />
                            {meeting.location}
                          </span>
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Badge tone="outline">{titleCase(meeting.meeting_type)}</Badge>
                        <Badge tone="primary">{formatRelative(meeting.starts_at)}</Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </>
        )}
      </DataState>
    </div>
  );
}
