"use client";

/** Advisor client list with search. */

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, Search, Users } from "lucide-react";

import { formatCurrency, formatDate, titleCase } from "@/lib/format";
import { useApi } from "@/lib/use-api";
import { Badge, Button, Card, CardHeader, Input, TD, TH, THead, TR, Table } from "@/components/ui";
import { PageHeader, StatRow, StatTile } from "@/components/shared/page";
import { DataState, LoadingTable, NoResults } from "@/components/shared/states";

type ClientRow = {
  household_id: string;
  name: string;
  segment: string;
  risk_profile: string;
  city: string | null;
  state: string | null;
  since: string | null;
  primary_advisor: string;
  primary_contact: string;
  client_count: number;
  account_count: number;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  goal_count: number;
  goals_off_track: number;
  pending_approvals: number;
  next_meeting: string | null;
  status: string;
};

type ClientsPayload = {
  clients: ClientRow[];
  total: number;
  summary: { total_aum: number; households: number; pending_approvals: number; goals_off_track: number };
};

export default function AdvisorClientsPage() {
  const [search, setSearch] = useState("");
  const { data, error, loading, refetch } = useApi<ClientsPayload>("/api/advisor/clients");

  const filtered = useMemo(() => {
    if (!data) return [];
    const needle = search.trim().toLowerCase();
    if (!needle) return data.clients;
    return data.clients.filter(
      (client) =>
        client.name.toLowerCase().includes(needle) ||
        client.primary_contact.toLowerCase().includes(needle) ||
        (client.city ?? "").toLowerCase().includes(needle),
    );
  }, [data, search]);

  return (
    <div className="space-y-6">
      <PageHeader title="Clients" description="Every household in your book, with the figures that matter at a glance." />

      {data ? (
        <StatRow columns={4}>
          <StatTile label="Households" value={String(data.summary.households)} icon={Users} tone="primary" />
          <StatTile label="Assets under advice" value={formatCurrency(data.summary.total_aum, { compact: true })} />
          <StatTile
            label="Pending approvals"
            value={String(data.summary.pending_approvals)}
            tone={data.summary.pending_approvals ? "warning" : "positive"}
          />
          <StatTile
            label="Goals off track"
            value={String(data.summary.goals_off_track)}
            tone={data.summary.goals_off_track ? "warning" : "positive"}
          />
        </StatRow>
      ) : null}

      <Card>
        <CardHeader
          title="Book of business"
          action={
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-subtle" aria-hidden />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search households"
                className="h-8 w-56 pl-8 text-xs"
                aria-label="Search households"
              />
            </div>
          }
        />

        <DataState
          loading={loading}
          error={error}
          data={data}
          onRetry={refetch}
          loadingFallback={<LoadingTable rows={6} />}
          emptyWhen={() => filtered.length === 0}
          empty={<NoResults query={search} onClear={() => setSearch("")} />}
        >
          {() => (
            <Table>
              <THead>
                <TR>
                  <TH>Household</TH>
                  <TH>Segment</TH>
                  <TH align="right">Assets</TH>
                  <TH align="right">Liabilities</TH>
                  <TH align="right">Net worth</TH>
                  <TH align="right">Accounts</TH>
                  <TH align="right">Goals</TH>
                  <TH>Lead advisor</TH>
                  <TH>Next meeting</TH>
                  <TH align="right"> </TH>
                </TR>
              </THead>
              <tbody>
                {filtered.map((client) => (
                  <TR key={client.household_id}>
                    <TD>
                      <Link href={`/advisor/clients/${client.household_id}`} className="block">
                        <span className="font-medium text-ink hover:text-primary">{client.name}</span>
                        <span className="mt-0.5 block text-xs text-ink-muted">
                          {client.primary_contact}
                          {client.city ? ` · ${client.city}, ${client.state}` : ""}
                        </span>
                        {client.since ? (
                          <span className="mt-0.5 block text-2xs text-ink-subtle">Client since {formatDate(client.since)}</span>
                        ) : null}
                      </Link>
                    </TD>
                    <TD>
                      <Badge tone="outline" size="sm">{titleCase(client.segment)}</Badge>
                      <span className="mt-1 block text-2xs text-ink-subtle">{titleCase(client.risk_profile)}</span>
                    </TD>
                    <TD align="right" numeric className="font-medium">{formatCurrency(client.total_assets, { compact: true })}</TD>
                    <TD align="right" numeric className="text-ink-muted">{formatCurrency(client.total_liabilities, { compact: true })}</TD>
                    <TD align="right" numeric className="font-medium">{formatCurrency(client.net_worth, { compact: true })}</TD>
                    <TD align="right" numeric className="text-ink-muted">{client.account_count}</TD>
                    <TD align="right">
                      <span className="tabular">{client.goal_count}</span>
                      {client.goals_off_track > 0 ? (
                        <Badge tone="warning" size="sm" className="ml-1.5">{client.goals_off_track}</Badge>
                      ) : null}
                    </TD>
                    <TD className="text-xs">{client.primary_advisor}</TD>
                    <TD className="whitespace-nowrap text-xs text-ink-muted">
                      {client.next_meeting ? formatDate(client.next_meeting) : "—"}
                    </TD>
                    <TD align="right">
                      <Link href={`/advisor/clients/${client.household_id}`}>
                        <Button variant="ghost" size="icon-sm" aria-label={`Open ${client.name}`}>
                          <ChevronRight />
                        </Button>
                      </Link>
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
