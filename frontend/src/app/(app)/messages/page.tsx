"use client";

/** Secure messaging (§26). */

import { useEffect, useState } from "react";
import { MessageSquare, Paperclip, Send } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime, formatRelative, initialsOf, titleCase, truncate } from "@/lib/format";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardHeader, Input, Textarea } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { PageHeader } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable } from "@/components/shared/states";

type ThreadSummary = {
  id: string;
  subject: string;
  topic: string;
  status: string;
  message_count: number;
  unread_count: number;
  last_message_at: string | null;
  last_message_preview: string | null;
  last_sender: string | null;
};

type ThreadDetail = ThreadSummary & {
  messages: {
    id: string;
    sender_name: string;
    sender_role: string;
    body: string;
    sent_at: string;
    read_at: string | null;
    attachment_name: string | null;
  }[];
  action_items: { id: string; title: string; owner: string; status: string; due_date: string | null }[];
};

export default function MessagesPage() {
  const { user } = useAuth();
  const { data, error, loading, refetch } = useApi<{ threads: ThreadSummary[] }>("/api/messages");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [threadLoading, setThreadLoading] = useState(false);
  const [reply, setReply] = useState("");

  useEffect(() => {
    if (!activeId && data?.threads.length) setActiveId(data.threads[0].id);
  }, [data, activeId]);

  useEffect(() => {
    if (!activeId) return;
    setThreadLoading(true);
    api
      .get<ThreadDetail>(`/api/messages/${activeId}`)
      .then((payload) => {
        setThread(payload);
        api.post(`/api/messages/${activeId}/read`).catch(() => null);
      })
      .catch(() => setThread(null))
      .finally(() => setThreadLoading(false));
  }, [activeId]);

  const { run: send, pending } = useMutation(async () => {
    if (!activeId || !reply.trim()) return null;
    await api.post(`/api/messages/${activeId}/reply`, { body: reply.trim() });
    const refreshed = await api.get<ThreadDetail>(`/api/messages/${activeId}`);
    setThread(refreshed);
    setReply("");
    refetch();
    return refreshed;
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Messages"
        description="Secure conversations with your advisory team. Everything here stays inside the platform."
      />

      <DataState
        loading={loading}
        error={error}
        data={data}
        onRetry={refetch}
        loadingFallback={<LoadingTable rows={5} />}
        emptyWhen={(payload) => payload.threads.length === 0}
        empty={
          <Card>
            <EmptyState icon={MessageSquare} title="No conversations yet" description="Messages from your advisory team appear here." />
          </Card>
        }
      >
        {(payload) => (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,320px)_1fr]">
            <Card className="h-fit">
              <CardHeader title="Conversations" description={`${payload.threads.length} threads`} />
              <ul className="divide-y divide-border">
                {payload.threads.map((item) => (
                  <li key={item.id}>
                    <button
                      onClick={() => setActiveId(item.id)}
                      className={cn(
                        "w-full px-4 py-3.5 text-left transition-colors",
                        item.id === activeId ? "bg-primary-soft/50" : "hover:bg-surface-muted/70",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="min-w-0 truncate text-sm font-medium text-ink">{item.subject}</p>
                        {item.unread_count > 0 ? (
                          <span className="flex size-4 shrink-0 items-center justify-center rounded-full bg-primary text-[0.5625rem] font-semibold text-primary-foreground">
                            {item.unread_count}
                          </span>
                        ) : null}
                      </div>
                      {item.last_message_preview ? (
                        <p className="mt-1 line-clamp-2 text-xs leading-5 text-ink-muted">
                          {truncate(item.last_message_preview, 96)}
                        </p>
                      ) : null}
                      <div className="mt-1.5 flex items-center gap-2">
                        <Badge tone="outline" size="sm">
                          {titleCase(item.topic)}
                        </Badge>
                        <span className="text-2xs text-ink-subtle">
                          {item.last_message_at ? formatRelative(item.last_message_at) : "—"}
                        </span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="flex min-h-[32rem] flex-col">
              {threadLoading && !thread ? (
                <div className="flex-1 p-5">
                  <LoadingTable rows={4} />
                </div>
              ) : !thread ? (
                <EmptyState title="Select a conversation" description="Choose a thread on the left to read it." />
              ) : (
                <>
                  <CardHeader
                    title={thread.subject}
                    description={`${thread.message_count} messages · ${titleCase(thread.topic)}`}
                    action={<StatusBadge status={thread.status} />}
                  />

                  <div className="flex-1 space-y-4 overflow-y-auto p-5">
                    {thread.messages.map((message) => {
                      const mine = message.sender_role === user?.role && message.sender_name === user?.full_name;
                      return (
                        <div key={message.id} className={cn("flex gap-3", mine && "flex-row-reverse")}>
                          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-muted text-2xs font-semibold text-ink-muted">
                            {initialsOf(message.sender_name)}
                          </span>
                          <div className={cn("max-w-[75%]", mine && "text-right")}>
                            <p className="flex items-center gap-2 text-2xs text-ink-subtle" style={{ justifyContent: mine ? "flex-end" : undefined }}>
                              <span className="font-medium text-ink-muted">{message.sender_name}</span>
                              <span>{titleCase(message.sender_role)}</span>
                              <span>· {formatDateTime(message.sent_at)}</span>
                            </p>
                            <div
                              className={cn(
                                "mt-1 rounded-lg px-3.5 py-2.5 text-sm leading-6",
                                mine
                                  ? "rounded-br-sm bg-primary text-primary-foreground"
                                  : "rounded-bl-sm border border-border bg-surface-muted/70 text-ink",
                              )}
                            >
                              {message.body}
                            </div>
                            {message.attachment_name ? (
                              <p className="mt-1 flex items-center gap-1 text-2xs text-ink-muted" style={{ justifyContent: mine ? "flex-end" : undefined }}>
                                <Paperclip className="size-3" aria-hidden />
                                {message.attachment_name}
                              </p>
                            ) : null}
                            {!mine && message.read_at ? (
                              <p className="mt-0.5 text-2xs text-ink-subtle">Read {formatRelative(message.read_at)}</p>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {thread.action_items.length > 0 ? (
                    <div className="border-t border-border bg-surface-muted/50 px-5 py-3">
                      <p className="section-label">Action items from this thread</p>
                      <ul className="mt-2 space-y-1.5">
                        {thread.action_items.map((item) => (
                          <li key={item.id} className="flex items-center justify-between gap-3 text-xs">
                            <span className="text-ink">{item.title}</span>
                            <span className="flex items-center gap-2">
                              <span className="text-ink-muted">{item.owner}</span>
                              <StatusBadge status={item.status} />
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      send();
                    }}
                    className="space-y-2 border-t border-border p-4"
                  >
                    <Textarea
                      value={reply}
                      onChange={(event) => setReply(event.target.value)}
                      rows={3}
                      placeholder="Write a reply…"
                      aria-label="Reply"
                    />
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-2xs text-ink-subtle">
                        Messages are stored inside Nexgile and recorded in the activity trail.
                      </p>
                      <Button type="submit" variant="primary" size="sm" loading={pending} disabled={!reply.trim()}>
                        <Send />
                        Send
                      </Button>
                    </div>
                  </form>
                </>
              )}
            </Card>
          </div>
        )}
      </DataState>
    </div>
  );
}
