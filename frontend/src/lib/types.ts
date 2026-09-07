/** Shapes returned by the Nexgile API. Kept close to the backend schemas. */

export type Role =
  | "client"
  | "plan_sponsor"
  | "participant"
  | "advisor"
  | "investment_team"
  | "tax_specialist"
  | "estate_trust"
  | "compliance"
  | "operations"
  | "admin";

export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type Freshness = "fresh" | "delayed" | "stale" | "unavailable";
export type ApprovalStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "approved"
  | "rejected"
  | "cancelled"
  | "completed";

export type UserProfile = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  role_label: string;
  title: string | null;
  avatar_initials: string;
  permissions: string[];
  home_route: string;
  client_id: string | null;
  household_id: string | null;
  is_demo: boolean;
  last_login_at: string | null;
  timezone: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: UserProfile;
};

export type DemoAccount = {
  label: string;
  email: string;
  role: Role;
  role_label: string;
  full_name: string;
  title: string | null;
  home_route: string;
};

/** Every financial figure arrives wrapped in its own disclosure (§4). */
export type Calculation<T = Record<string, unknown>> = {
  method: string;
  result: T;
  as_of: string;
  inputs: Record<string, unknown>;
  assumptions: string[];
  limitations: string[];
  source: string;
  computed_at: string;
};

export type NetWorthResult = {
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  by_account_type: Record<string, number>;
  leverage_ratio: number;
};

export type ValuationResult = {
  market_value: number;
  cost_basis: number;
  unrealized_gain: number;
  unrealized_gain_percent: number;
  day_change: number;
  day_change_percent: number;
  cash: number;
};

export type AllocationRow = {
  key: string;
  label: string;
  market_value: number;
  weight: number;
};

export type DriftRow = {
  asset_class: string;
  label: string;
  current_weight: number;
  target_weight: number;
  drift: number;
  tolerance_band: number;
  breached: boolean;
  dollar_drift: number;
};

export type ConcentrationRow = {
  symbol: string;
  name: string;
  security_type: string;
  is_single_name: boolean;
  market_value: number;
  weight: number;
  exceeds_threshold: boolean;
};

export type PeriodReturn = {
  period: string;
  return: number;
  benchmark_return: number;
  excess_return: number;
  annualized_return: number | null;
  start_value: number;
  end_value: number;
  points: number;
};

export type PerformancePayload = {
  as_of: string;
  benchmark: { code: string; name: string } | null;
  periods: Record<string, PeriodReturn>;
  risk_adjusted: Calculation<{
    volatility: number;
    annualized_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    tracking_error: number;
    information_ratio: number;
  }>;
  series: { as_of: string; market_value: number; portfolio_index: number; benchmark_index: number }[];
};

export type GoalRow = {
  id: string;
  name: string;
  goal_type: string;
  priority: string;
  target_amount: number;
  current_amount: number;
  target_date: string;
  projected_value: number;
  inflation_adjusted_target: number;
  gap: number;
  funded_ratio: number;
  progress_percent: number;
  status: "on_track" | "monitor" | "at_risk" | "off_track";
  required_monthly_contribution: number;
  additional_monthly_needed: number;
  months_to_target: number;
  years_to_target: number;
};

export type HoldingRow = {
  holding_id: string;
  security_id: string;
  account_id: string;
  account_name: string;
  symbol: string;
  name: string;
  asset_class: string;
  asset_class_label: string;
  sector: string;
  region: string;
  quantity: number;
  price: number;
  average_cost: number;
  market_value: number;
  cost_basis: number;
  gain_loss: number;
  gain_loss_percent: number;
  day_change: number;
  day_change_percent: number;
  weight: number;
  dividend_yield: number;
  price_status: string;
};

export type AccountRow = {
  id: string;
  name: string;
  account_number_masked: string;
  account_type: string;
  account_subtype: string | null;
  tax_treatment: string;
  registration: string;
  balance: number;
  cash_balance: number;
  currency: string;
  is_liability: boolean;
  interest_rate: number | null;
  minimum_payment: number | null;
  status: string;
  is_external: boolean;
  opened_on: string | null;
  institution: string;
  connection_type: string;
  last_synced_at: string | null;
  data_freshness: Freshness;
  data_source: string;
};

export type SupportingFact = {
  label: string;
  value: string;
  raw_value: number | null;
  source: string;
  as_of: string | null;
};

export type Insight = {
  key: string;
  title: string;
  category: string;
  severity: Severity;
  summary: string;
  impact: string;
  suggested_next_step: string;
  supporting_facts: SupportingFact[];
  calculation_method: string | null;
  assumptions: string[];
  limitations: string[];
  confidence: number;
  as_of: string | null;
  source: string;
  entity_type: string | null;
  entity_id: string | null;
  action_url: string | null;
};

export type RecommendationDraft = {
  key: string;
  title: string;
  category: string;
  severity: Severity;
  summary: string;
  rationale: string;
  suggested_action: string;
  impact_amount: number | null;
  impact_label: string | null;
  confidence: number;
  supporting_data: Record<string, unknown>;
  assumptions: string[];
  limitations: string[];
  requires_approval: boolean;
  entity_type: string | null;
  entity_id: string | null;
};

export type NextAction = {
  key: string;
  label: string;
  description: string;
  route: string;
  category: string;
  requires_approval: boolean;
  severity: Severity;
};

export type Recommendation = {
  id: string;
  household_id: string;
  title: string;
  category: string;
  severity: Severity;
  summary: string;
  rationale: string;
  suggested_action: string;
  impact_amount: number | null;
  impact_label: string | null;
  confidence: number;
  status: string;
  source: string;
  generator: string;
  assumptions: string[];
  limitations: string[];
  approval_id: string | null;
  as_of: string | null;
  created_at: string;
};

export type ApprovalEvent = {
  id: string;
  from_status: string | null;
  to_status: ApprovalStatus;
  actor_name: string;
  note: string | null;
  created_at: string;
};

export type Approval = {
  id: string;
  title: string;
  summary: string | null;
  entity_type: string;
  entity_id: string | null;
  status: ApprovalStatus;
  priority: string;
  household_id: string | null;
  household: string | null;
  requested_by: string;
  decided_by: string | null;
  required_role: string;
  estimated_impact: number | null;
  decision_note: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  submitted_at: string | null;
  decided_at: string | null;
  completed_at: string | null;
  due_date: string | null;
  available_transitions: ApprovalStatus[];
  events: ApprovalEvent[];
};

export type AuditEvent = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  entity_label: string | null;
  actor_name: string;
  actor_role: string | null;
  household_id: string | null;
  status: string;
  summary: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
};

export type Notification = {
  id: string;
  category: string;
  category_label: string;
  severity: Severity;
  title: string;
  body: string;
  entity_type: string | null;
  entity_id: string | null;
  action_url: string | null;
  due_date: string | null;
  is_read: boolean;
  created_at: string;
};

export type DocumentRow = {
  id: string;
  name: string;
  original_filename: string;
  category: string;
  document_type: string | null;
  tax_year: number | null;
  tags: string[];
  description: string | null;
  mime_type: string;
  size_bytes: number;
  current_version: number;
  review_status: string;
  uploaded_by: string;
  uploaded_at: string;
  expires_on: string | null;
  retention_until: string | null;
  is_confidential: boolean;
  is_expired: boolean;
  expires_soon: boolean;
  storage_backend: string;
  classification: {
    suggested_category: string;
    suggested_document_type: string;
    confidence: number;
    source: string;
    reasons: string[];
    accepted: boolean | null;
    note: string;
  } | null;
};

export type DashboardPayload = {
  household: { id: string; name: string };
  as_of: string;
  net_worth: Calculation<NetWorthResult>;
  net_worth_trend: { period: string; as_of: string; portfolio_value: number; net_worth: number }[];
  portfolio: Calculation<ValuationResult>;
  allocation: Calculation<{ total: number; rows: AllocationRow[] }>;
  concentration: Calculation<{
    rows: ConcentrationRow[];
    top_position: ConcentrationRow | null;
    top_single_name: ConcentrationRow | null;
    single_name_weight: number;
    top_five_weight: number;
    hhi: number;
    flagged: ConcentrationRow[];
  }>;
  risk: Calculation<{ beta: number; volatility: number; equity_exposure: number; cash_exposure: number }>;
  performance: PerformancePayload;
  top_holdings: HoldingRow[];
  goals: Calculation<{
    goals: GoalRow[];
    total_target: number;
    total_current: number;
    overall_progress: number;
    goals_off_track: number;
    goal_count: number;
  }>;
  needs_attention: {
    key: string;
    title: string;
    category: string;
    severity: Severity;
    summary: string;
    action_url: string | null;
  }[];
  wealthagent: {
    provider: { name: string; mode: string; description: string };
    insights: Insight[];
    actions: NextAction[];
  };
  notifications: { notifications: Notification[]; unread_count: number };
  next_meeting: { id: string; title: string; starts_at: string; agenda: string[] } | null;
  data_freshness: Record<string, Freshness>;
};
