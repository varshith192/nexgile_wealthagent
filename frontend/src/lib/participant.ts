/** Shapes for the participant portal (§33-§35). */

import type { Calculation } from "@/lib/types";

export type ParticipantProfile = {
  id: string;
  full_name: string;
  employee_id_masked: string;
  age: number;
  hire_date: string;
  years_of_service: number;
  annual_salary: number;
  deferral_rate: number;
  roth_deferral_rate: number;
  account_balance: number;
  roth_balance: number;
  employer_balance: number;
  vested_percentage: number;
  vested_balance: number;
  is_hce: boolean;
  is_auto_enrolled: boolean;
  has_beneficiary: boolean;
  retirement_age: number;
  status: string;
  engagement_score: number;
};

export type RetirementProjection = Calculation<{
  projected_balance: number;
  portfolio_income: number;
  social_security_income: number;
  other_income: number;
  healthcare_costs: number;
  total_projected_income: number;
  target_income: number;
  income_gap: number;
  replacement_ratio: number;
  required_balance: number;
  balance_gap: number;
  additional_annual_contribution: number;
  readiness_score: number;
  status: string;
  years_to_retirement: number;
  years_in_retirement: number;
}>;

export type Readiness = {
  projection: RetirementProjection;
  monte_carlo: Calculation<{
    trials: number;
    success_rate: number;
    success_basis: string;
    success_threshold: number | null;
    successful_trials: number;
    depletion_count: number;
    percentiles: { p10: number; p25: number; p50: number; p75: number; p90: number };
    median_ending_balance: number;
    deterministic_projection: number;
  }>;
  scenarios: {
    label: string;
    is_baseline: boolean;
    projected_balance: number;
    total_projected_income: number;
    target_income: number;
    income_gap: number;
    replacement_ratio: number;
    status: string;
  }[];
  inputs: {
    current_age: number;
    retirement_age: number;
    annual_income: number;
    deferral_rate: number;
    current_savings: number;
    employer_match_formula: string | null;
    expected_return: number;
  };
};

export type ParticipantPortal = {
  participant: ParticipantProfile;
  plan: {
    id: string;
    name: string;
    plan_type: string;
    sponsor: string;
    employer_match_formula: string;
    vesting_schedule: string;
    auto_enrollment: boolean;
    auto_escalation: boolean;
    loans_allowed: boolean;
    recordkeeper: string;
  };
  as_of: string;
  contributions: {
    ytd_employee: number;
    ytd_employer: number;
    history: {
      period_end: string;
      employee_pretax: number;
      employee_roth: number;
      employee_catchup: number;
      employer_match: number;
      employer_profit_sharing: number;
      total: number;
    }[];
    capacity: Calculation<{
      annual_limit: number;
      catchup_eligible: boolean;
      catchup_amount: number;
      projected_deferral: number;
      ytd_deferral: number;
      remaining_capacity: number;
      on_pace_to_max: boolean;
      required_rate_to_max: number;
    }>;
  };
  vesting: Calculation<{ vested_percentage: number; years_of_service: number; schedule: string; fully_vested: boolean }>;
  loans: {
    id: string;
    original_amount: number;
    outstanding_balance: number;
    interest_rate: number;
    term_months: number;
    payment_amount: number;
    issued_on: string;
    matures_on: string;
    loan_type: string;
    status: string;
  }[];
  investments: {
    id: string;
    name: string;
    ticker: string | null;
    asset_category: string;
    expense_ratio: number;
    three_year_return: number;
    five_year_return: number;
    is_qdia: boolean;
    ips_status: string;
  }[];
  readiness: Readiness;
  beneficiaries: { has_beneficiary: boolean; note: string };
  education: {
    items: {
      id: string;
      title: string;
      content_type: string;
      learning_path: string;
      level: string;
      duration_minutes: number;
      summary: string;
      body: string | null;
      status: string;
      progress_percent: number;
      score: number | null;
      completed_at: string | null;
    }[];
    paths: { learning_path: string; total: number; completed: number; progress: number }[];
    completion_rate: number;
  };
};
