/**
 * Role-aware navigation (§8).
 *
 * Each role sees the workspace it works in. Anything a role cannot reach is
 * absent from the sidebar rather than shown and then refused.
 */

import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BadgeCheck,
  BarChart3,
  Briefcase,
  Building2,
  CalendarDays,
  CheckSquare,
  ClipboardList,
  Coins,
  FileText,
  GraduationCap,
  HandCoins,
  Landmark,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  PieChart,
  Radar,
  Receipt,
  Scale,
  ScrollText,
  Target,
  Users,
  Wallet,
} from "lucide-react";

import type { Role } from "@/lib/types";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  description?: string;
  exact?: boolean;
};

export type NavSection = {
  title: string;
  items: NavItem[];
};

const CLIENT_NAV: NavSection[] = [
  {
    title: "Wealth",
    items: [
      { label: "Overview", href: "/dashboard", icon: LayoutDashboard, exact: true, description: "Net worth, portfolio and what needs attention" },
      { label: "Portfolio", href: "/portfolio", icon: PieChart, description: "Allocation, performance and risk" },
      { label: "Accounts", href: "/accounts", icon: Wallet, description: "Every linked account and balance" },
      { label: "Holdings", href: "/holdings", icon: BarChart3, description: "Positions, cost basis and gain/loss" },
      { label: "Goals", href: "/goals", icon: Target, description: "Funding progress and scenarios" },
    ],
  },
  {
    title: "Planning",
    items: [
      { label: "Tax", href: "/tax", icon: Receipt, description: "Opportunities, harvesting and projections" },
      { label: "Estate", href: "/estate", icon: Scale, description: "Wills, trusts and beneficiaries" },
      { label: "Philanthropy", href: "/philanthropy", icon: HandCoins, description: "Giving, grants and deduction impact" },
    ],
  },
  {
    title: "Service",
    items: [
      { label: "Documents", href: "/documents", icon: FileText },
      { label: "Messages", href: "/messages", icon: MessageSquare },
      { label: "Meetings", href: "/meetings", icon: CalendarDays },
      { label: "Reports", href: "/reports", icon: ClipboardList },
    ],
  },
  {
    title: "Intelligence",
    items: [{ label: "WealthAgent", href: "/wealthagent", icon: Radar, description: "Insights, recommendations and actions" }],
  },
];

const ADVISOR_NAV: NavSection[] = [
  {
    title: "Practice",
    items: [
      { label: "Workstation", href: "/advisor", icon: LayoutDashboard, exact: true, description: "Book, alerts and approvals" },
      { label: "Clients", href: "/advisor/clients", icon: Users, description: "Households and Client 360" },
      { label: "Portfolio Tools", href: "/advisor/portfolio", icon: PieChart, description: "Risk, frontier and stress tests" },
      { label: "Rebalancing", href: "/advisor/rebalancing", icon: Activity, description: "Drift, trade proposals and approval" },
      { label: "Tax Planning", href: "/advisor/tax", icon: Receipt, description: "Harvesting and opportunities" },
    ],
  },
  {
    title: "Workflow",
    items: [
      { label: "Approvals", href: "/approvals", icon: BadgeCheck },
      { label: "Tasks", href: "/advisor/tasks", icon: CheckSquare },
      { label: "Meetings", href: "/advisor/meetings", icon: CalendarDays },
      { label: "Reports", href: "/advisor/reports", icon: ClipboardList },
    ],
  },
  {
    title: "Oversight",
    items: [
      { label: "Compliance", href: "/advisor/compliance", icon: ScrollText },
      { label: "Audit Trail", href: "/audit", icon: ListChecks },
    ],
  },
];

const SPONSOR_NAV: NavSection[] = [
  {
    title: "Plan",
    items: [
      { label: "Overview", href: "/institutional", icon: LayoutDashboard, exact: true, description: "Plan health and engagement" },
      { label: "Plans", href: "/institutional/plans", icon: Building2 },
      { label: "Participants", href: "/institutional/participants", icon: Users },
      { label: "Investments", href: "/institutional/investments", icon: Landmark, description: "Fiduciary lineup and IPS screening" },
      { label: "Plan Costs", href: "/institutional/fees", icon: Coins },
    ],
  },
  {
    title: "Governance",
    items: [
      { label: "Compliance", href: "/institutional/compliance", icon: ScrollText },
      { label: "Approvals", href: "/approvals", icon: BadgeCheck },
    ],
  },
];

const PARTICIPANT_NAV: NavSection[] = [
  {
    title: "My Plan",
    items: [
      { label: "Overview", href: "/participant", icon: LayoutDashboard, exact: true },
      { label: "Retirement", href: "/participant/retirement", icon: Target, description: "Readiness and projections" },
      { label: "Contributions", href: "/participant/contributions", icon: Coins },
      { label: "Investments", href: "/participant/investments", icon: PieChart },
      { label: "Loans", href: "/participant/loans", icon: Briefcase },
      { label: "Beneficiaries", href: "/participant/beneficiaries", icon: Scale },
    ],
  },
  {
    title: "Learn",
    items: [{ label: "Education", href: "/participant/education", icon: GraduationCap }],
  },
];

const COMPLIANCE_NAV: NavSection[] = [
  {
    title: "Oversight",
    items: [
      { label: "Compliance Center", href: "/compliance", icon: ScrollText, exact: true },
      { label: "Approvals", href: "/approvals", icon: BadgeCheck },
      { label: "Audit Trail", href: "/audit", icon: ListChecks },
      { label: "Clients", href: "/advisor/clients", icon: Users },
      { label: "Investments", href: "/institutional/investments", icon: Landmark },
    ],
  },
];

const ADMIN_NAV: NavSection[] = [
  {
    title: "Leadership",
    items: [
      { label: "Overview", href: "/admin", icon: LayoutDashboard, exact: true },
      { label: "Advisor Workstation", href: "/advisor", icon: Briefcase },
      { label: "Clients", href: "/advisor/clients", icon: Users },
      { label: "Institutional", href: "/institutional", icon: Building2 },
    ],
  },
  {
    title: "Control",
    items: [
      { label: "Approvals", href: "/approvals", icon: BadgeCheck },
      { label: "Compliance", href: "/compliance", icon: ScrollText },
      { label: "Audit Trail", href: "/audit", icon: ListChecks },
    ],
  },
  {
    title: "Client View",
    items: [
      { label: "Client Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { label: "WealthAgent", href: "/wealthagent", icon: Radar },
    ],
  },
];

export const NAVIGATION: Record<Role, NavSection[]> = {
  client: CLIENT_NAV,
  advisor: ADVISOR_NAV,
  investment_team: ADVISOR_NAV,
  tax_specialist: ADVISOR_NAV,
  estate_trust: ADVISOR_NAV,
  operations: ADVISOR_NAV,
  plan_sponsor: SPONSOR_NAV,
  participant: PARTICIPANT_NAV,
  compliance: COMPLIANCE_NAV,
  admin: ADMIN_NAV,
};

export function navigationFor(role: Role | undefined): NavSection[] {
  if (!role) return [];
  return NAVIGATION[role] ?? CLIENT_NAV;
}

export function isActivePath(pathname: string, item: NavItem): boolean {
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}
