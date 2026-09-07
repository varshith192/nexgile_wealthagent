"use client";

/**
 * Document vault (§18).
 *
 * Uploads receive a suggested filing from the platform's deterministic rules
 * engine. The suggestion is always presented as a suggestion — accept, edit or
 * reject — and it is never described as the work of an external model.
 */

import { useMemo, useRef, useState } from "react";
import {
  CheckCheck,
  CircleAlert,
  Clock,
  FileText,
  Pencil,
  Search,
  Sparkles,
  Upload,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import { formatBytes, formatDate, titleCase } from "@/lib/format";
import type { DocumentRow } from "@/lib/types";
import { useApi, useMutation } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { Badge, Button, Card, CardBody, CardHeader, Drawer, Input, Progress, Select } from "@/components/ui";
import { StatusBadge } from "@/components/shared/indicators";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, EmptyState, LoadingTable, NoResults } from "@/components/shared/states";

type DocumentsPayload = {
  documents: DocumentRow[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  categories: { key: string; label: string; count: number }[];
  tags: string[];
  summary: { total: number; pending_review: number; expiring_soon: number; expired: number };
  requests: { id: string; title: string; category: string; reason: string | null; due_date: string | null; status: string }[];
};

export default function DocumentsPage() {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [selected, setSelected] = useState<DocumentRow | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const path = useMemo(() => {
    const params = new URLSearchParams({ page_size: "50" });
    if (search.trim()) params.set("search", search.trim());
    if (category) params.set("category", category);
    if (reviewStatus) params.set("review_status", reviewStatus);
    return `/api/documents?${params.toString()}`;
  }, [search, category, reviewStatus]);

  const { data, error, loading, refetch } = useApi<DocumentsPayload>(path);

  const upload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const created = await api.upload<DocumentRow>("/api/documents", formData);
      refetch();
      setSelected(created);
    } catch (caught) {
      setUploadError(caught instanceof Error ? caught.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const clearFilters = () => {
    setSearch("");
    setCategory("");
    setReviewStatus("");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Documents"
        description="Your secure vault for tax, estate, investment, insurance and legal records."
        actions={
          <>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.png,.jpg,.jpeg,.txt,.md"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload(file);
              }}
            />
            <Button variant="primary" size="sm" loading={uploading} onClick={() => fileRef.current?.click()}>
              <Upload />
              Upload document
            </Button>
          </>
        }
      />

      {uploadError ? (
        <div role="alert" className="rounded-md border border-negative/25 bg-negative-soft px-4 py-3 text-sm text-negative">
          {uploadError}
        </div>
      ) : null}

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Documents" value={String(data.summary.total)} icon={FileText} tone="primary" />
          <StatTile
            label="Awaiting review"
            value={String(data.summary.pending_review)}
            tone={data.summary.pending_review ? "warning" : "positive"}
            icon={Clock}
          />
          <StatTile
            label="Expiring within 90 days"
            value={String(data.summary.expiring_soon)}
            tone={data.summary.expiring_soon ? "warning" : "default"}
            icon={CircleAlert}
          />
          <StatTile label="Open requests" value={String(data.requests.length)} hint="Documents your advisor has asked for" />
        </StatRow>
      ) : null}

      {data && data.requests.length > 0 ? (
        <Card className="border-info/25 bg-info-soft/40">
          <CardBody className="py-4">
            <p className="text-sm font-semibold text-ink">Your advisor has requested</p>
            <ul className="mt-2.5 space-y-2">
              {data.requests.map((request) => (
                <li key={request.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-surface px-3.5 py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">{request.title}</p>
                    {request.reason ? <p className="mt-0.5 text-xs text-ink-muted">{request.reason}</p> : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge tone="outline">{titleCase(request.category)}</Badge>
                    {request.due_date ? (
                      <span className="text-xs text-ink-muted">by {formatDate(request.due_date)}</span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Vault"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-subtle" aria-hidden />
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search documents"
                  className="h-8 w-48 pl-8 text-xs"
                  aria-label="Search documents"
                />
              </div>
              <Select
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="h-8 w-44 text-xs"
                aria-label="Filter by category"
              >
                <option value="">All categories</option>
                {data?.categories.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label} ({option.count})
                  </option>
                ))}
              </Select>
              <Select
                value={reviewStatus}
                onChange={(event) => setReviewStatus(event.target.value)}
                className="h-8 w-40 text-xs"
                aria-label="Filter by review status"
              >
                <option value="">Any status</option>
                <option value="pending_review">Awaiting review</option>
                <option value="reviewed">Reviewed</option>
              </Select>
              {(search || category || reviewStatus) && (
                <Button size="sm" variant="ghost" onClick={clearFilters}>
                  <X />
                  Clear
                </Button>
              )}
            </div>
          }
        />

        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={8} />}
          emptyWhen={(payload) => payload.documents.length === 0}
          empty={
            search || category || reviewStatus ? (
              <NoResults query={search} onClear={clearFilters} />
            ) : (
              <EmptyState
                icon={FileText}
                title="No documents yet"
                description="Upload a statement, tax return or estate document to get started."
                action={
                  <Button variant="primary" size="sm" onClick={() => fileRef.current?.click()}>
                    <Upload />
                    Upload document
                  </Button>
                }
              />
            )
          }
        >
          {(payload) => (
            <ul className="divide-y divide-border">
              {payload.documents.map((document) => (
                <li key={document.id}>
                  <button
                    onClick={() => setSelected(document)}
                    className="flex w-full items-center justify-between gap-4 px-5 py-3.5 text-left transition-colors hover:bg-surface-muted/70"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-surface-muted">
                        <FileText className="size-4 text-ink-subtle" aria-hidden />
                      </span>
                      <div className="min-w-0">
                        <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink">
                          <span className="truncate">{document.name}</span>
                          {document.review_status === "pending_review" ? (
                            <Badge tone="warning" size="sm">Needs review</Badge>
                          ) : null}
                          {document.is_expired ? <Badge tone="negative" size="sm">Expired</Badge> : null}
                          {document.expires_soon && !document.is_expired ? (
                            <Badge tone="warning" size="sm">Expires soon</Badge>
                          ) : null}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-ink-muted">
                          {document.document_type ?? titleCase(document.category)}
                          {document.tax_year ? ` · ${document.tax_year}` : ""} · {formatBytes(document.size_bytes)} ·
                          uploaded {formatDate(document.uploaded_at)} by {document.uploaded_by}
                        </p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge tone="outline">{titleCase(document.category)}</Badge>
                      {document.classification ? (
                        <Badge tone="primary" size="sm">
                          <Sparkles className="size-3" />
                          {Math.round(document.classification.confidence * 100)}%
                        </Badge>
                      ) : null}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </DataState>
      </Card>

      <DocumentDrawer document={selected} onClose={() => setSelected(null)} onUpdated={refetch} />
    </div>
  );
}

function DocumentDrawer({
  document,
  onClose,
  onUpdated,
}: {
  document: DocumentRow | null;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editCategory, setEditCategory] = useState("");

  const { run: decide, pending, message } = useMutation(async (decision: "accept" | "edit" | "reject", categoryValue?: string) => {
    if (!document) return null;
    const result = await api.post<DocumentRow>(`/api/documents/${document.id}/classification`, {
      decision,
      category: categoryValue,
    });
    onUpdated();
    onClose();
    setEditing(false);
    return result;
  });

  if (!document) return <Drawer open={false} onClose={onClose} title="Document">{null}</Drawer>;

  const classification = document.classification;

  return (
    <Drawer
      open={Boolean(document)}
      onClose={onClose}
      title={document.name}
      description={`${titleCase(document.category)} · ${formatBytes(document.size_bytes)} · version ${document.current_version}`}
    >
      <div className="space-y-6">
        {/* --------------------------------------- Suggested filing */}
        {classification ? (
          <section className="rounded-lg border border-primary/25 bg-primary-soft/40 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                  <Sparkles className="size-4 text-primary" aria-hidden />
                  Suggested filing
                </p>
                <p className="mt-1 text-xs leading-relaxed text-ink-muted">{classification.note}</p>
              </div>
              <Badge tone="primary">{Math.round(classification.confidence * 100)}% confidence</Badge>
            </div>

            <dl className="mt-4 space-y-2 border-t border-primary/15 pt-3">
              <Row label="Suggested category" value={titleCase(classification.suggested_category)} />
              <Row label="Document type" value={classification.suggested_document_type} />
              {document.tax_year ? <Row label="Detected year" value={String(document.tax_year)} /> : null}
              <Row label="Source" value="Deterministic rules engine" />
            </dl>

            <Progress value={classification.confidence} tone={classification.confidence > 0.8 ? "positive" : "warning"} className="mt-3" />

            {classification.reasons.length > 0 ? (
              <ul className="mt-3 list-disc space-y-1 pl-4 text-xs leading-relaxed text-ink-muted">
                {classification.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            ) : null}

            {classification.accepted === null ? (
              editing ? (
                <div className="mt-4 space-y-2.5">
                  <Select value={editCategory} onChange={(event) => setEditCategory(event.target.value)} aria-label="Choose a category">
                    <option value="">Choose a category…</option>
                    {["tax", "estate", "investment", "insurance", "banking", "retirement", "legal", "other"].map((option) => (
                      <option key={option} value={option}>
                        {titleCase(option)}
                      </option>
                    ))}
                  </Select>
                  <div className="flex gap-2">
                    <Button size="sm" variant="primary" loading={pending} disabled={!editCategory} onClick={() => decide("edit", editCategory)}>
                      Save category
                    </Button>
                    <Button size="sm" onClick={() => setEditing(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" variant="primary" loading={pending} onClick={() => decide("accept")}>
                    <CheckCheck />
                    Accept
                  </Button>
                  <Button size="sm" onClick={() => setEditing(true)}>
                    <Pencil />
                    Edit
                  </Button>
                  <Button size="sm" variant="ghost" loading={pending} onClick={() => decide("reject", "other")}>
                    <X />
                    Reject
                  </Button>
                </div>
              )
            ) : (
              <Badge tone={classification.accepted ? "positive" : "neutral"} className="mt-4">
                {classification.accepted ? "Suggestion accepted" : "Filed manually"}
              </Badge>
            )}

            {message ? <p className="mt-3 text-xs text-negative">{message}</p> : null}
          </section>
        ) : null}

        <section>
          <h3 className="section-label">Details</h3>
          <dl className="mt-2.5 space-y-2">
            <Row label="Category" value={titleCase(document.category)} />
            <Row label="Type" value={document.document_type ?? "—"} />
            <Row label="Review status" value={<StatusBadge status={document.review_status} />} />
            <Row label="Uploaded" value={`${formatDate(document.uploaded_at)} by ${document.uploaded_by}`} />
            <Row label="Size" value={formatBytes(document.size_bytes)} />
            <Row label="Version" value={String(document.current_version)} />
            <Row label="Expires" value={document.expires_on ? formatDate(document.expires_on) : "No expiry recorded"} />
            <Row label="Retention until" value={document.retention_until ? formatDate(document.retention_until) : "—"} />
            <Row label="Confidential" value={document.is_confidential ? "Yes" : "No"} />
          </dl>
        </section>

        {document.tags.length > 0 ? (
          <section>
            <h3 className="section-label">Tags</h3>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {document.tags.map((tag) => (
                <Badge key={tag} tone="outline">
                  {tag}
                </Badge>
              ))}
            </div>
          </section>
        ) : null}

        {document.description ? (
          <section>
            <h3 className="section-label">Description</h3>
            <p className="mt-1.5 text-sm leading-6 text-ink-muted">{document.description}</p>
          </section>
        ) : null}
      </div>
    </Drawer>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border/60 pb-1.5">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="text-right text-xs font-medium text-ink">{value}</dd>
    </div>
  );
}
