"""Domain enums shared by models, schemas and services."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    CLIENT = "client"
    PLAN_SPONSOR = "plan_sponsor"
    PARTICIPANT = "participant"
    ADVISOR = "advisor"
    INVESTMENT_TEAM = "investment_team"
    TAX_SPECIALIST = "tax_specialist"
    ESTATE_TRUST = "estate_trust"
    COMPLIANCE = "compliance"
    OPERATIONS = "operations"
    ADMIN = "admin"


ROLE_LABELS: dict[str, str] = {
    Role.CLIENT: "Client",
    Role.PLAN_SPONSOR: "Plan Sponsor",
    Role.PARTICIPANT: "Participant",
    Role.ADVISOR: "Advisor",
    Role.INVESTMENT_TEAM: "Investment Team",
    Role.TAX_SPECIALIST: "Tax Specialist",
    Role.ESTATE_TRUST: "Estate & Trust",
    Role.COMPLIANCE: "Compliance",
    Role.OPERATIONS: "Operations",
    Role.ADMIN: "Admin / Leadership",
}

# Workspace each role lands in after sign-in.
ROLE_HOME: dict[str, str] = {
    Role.CLIENT: "/dashboard",
    Role.PARTICIPANT: "/participant",
    Role.PLAN_SPONSOR: "/institutional",
    Role.ADVISOR: "/advisor",
    Role.INVESTMENT_TEAM: "/advisor/portfolio",
    Role.TAX_SPECIALIST: "/advisor/tax",
    Role.ESTATE_TRUST: "/advisor/clients",
    Role.COMPLIANCE: "/compliance",
    Role.OPERATIONS: "/advisor/tasks",
    Role.ADMIN: "/admin",
}


class Permission(StrEnum):
    """Coarse capabilities checked server side on every protected route."""

    VIEW_OWN_WEALTH = "wealth:view_own"
    VIEW_CLIENT_WEALTH = "wealth:view_clients"
    MANAGE_GOALS = "goals:manage"
    VIEW_TAX = "tax:view"
    MANAGE_TAX = "tax:manage"
    VIEW_ESTATE = "estate:view"
    MANAGE_ESTATE = "estate:manage"
    MANAGE_DOCUMENTS = "documents:manage"
    CREATE_RECOMMENDATION = "recommendations:create"
    APPROVE = "approvals:decide"
    SUBMIT_APPROVAL = "approvals:submit"
    MANAGE_REBALANCE = "rebalance:manage"
    VIEW_INSTITUTIONAL = "institutional:view"
    MANAGE_INSTITUTIONAL = "institutional:manage"
    VIEW_PARTICIPANT = "participant:view"
    VIEW_COMPLIANCE = "compliance:view"
    MANAGE_COMPLIANCE = "compliance:manage"
    VIEW_AUDIT = "audit:view"
    ADMIN_ALL = "admin:all"


_CLIENT_BASE = {
    Permission.VIEW_OWN_WEALTH,
    Permission.MANAGE_GOALS,
    Permission.VIEW_TAX,
    Permission.VIEW_ESTATE,
    Permission.MANAGE_DOCUMENTS,
    Permission.SUBMIT_APPROVAL,
}

_ADVISOR_BASE = {
    Permission.VIEW_CLIENT_WEALTH,
    Permission.MANAGE_GOALS,
    Permission.VIEW_TAX,
    Permission.MANAGE_TAX,
    Permission.VIEW_ESTATE,
    Permission.MANAGE_DOCUMENTS,
    Permission.CREATE_RECOMMENDATION,
    Permission.SUBMIT_APPROVAL,
    Permission.APPROVE,
    Permission.MANAGE_REBALANCE,
    Permission.VIEW_AUDIT,
}

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    Role.CLIENT: set(_CLIENT_BASE),
    Role.PARTICIPANT: {Permission.VIEW_PARTICIPANT, Permission.MANAGE_DOCUMENTS, Permission.SUBMIT_APPROVAL},
    Role.PLAN_SPONSOR: {
        Permission.VIEW_INSTITUTIONAL,
        Permission.MANAGE_INSTITUTIONAL,
        Permission.VIEW_COMPLIANCE,
        Permission.MANAGE_DOCUMENTS,
        Permission.SUBMIT_APPROVAL,
        Permission.APPROVE,
    },
    Role.ADVISOR: set(_ADVISOR_BASE),
    Role.INVESTMENT_TEAM: set(_ADVISOR_BASE) | {Permission.VIEW_INSTITUTIONAL},
    Role.TAX_SPECIALIST: (set(_ADVISOR_BASE) - {Permission.MANAGE_REBALANCE}) | {Permission.MANAGE_TAX},
    Role.ESTATE_TRUST: (set(_ADVISOR_BASE) - {Permission.MANAGE_REBALANCE}) | {Permission.MANAGE_ESTATE},
    Role.COMPLIANCE: {
        Permission.VIEW_CLIENT_WEALTH,
        Permission.VIEW_COMPLIANCE,
        Permission.MANAGE_COMPLIANCE,
        Permission.VIEW_INSTITUTIONAL,
        Permission.VIEW_AUDIT,
        Permission.APPROVE,
        Permission.VIEW_TAX,
        Permission.VIEW_ESTATE,
    },
    Role.OPERATIONS: {
        Permission.VIEW_CLIENT_WEALTH,
        Permission.MANAGE_DOCUMENTS,
        Permission.VIEW_AUDIT,
        Permission.SUBMIT_APPROVAL,
        Permission.VIEW_INSTITUTIONAL,
    },
    Role.ADMIN: set(Permission),
}


class AccountType(StrEnum):
    BROKERAGE = "brokerage"
    RETIREMENT = "retirement"
    TRUST = "trust"
    EDUCATION = "education"
    BANKING = "banking"
    CREDIT = "credit"
    MORTGAGE = "mortgage"
    EXTERNAL = "external"


LIABILITY_ACCOUNT_TYPES = {AccountType.CREDIT, AccountType.MORTGAGE}


class AssetClass(StrEnum):
    US_EQUITY = "us_equity"
    INTL_EQUITY = "intl_equity"
    FIXED_INCOME = "fixed_income"
    CASH = "cash"
    ALTERNATIVES = "alternatives"
    REAL_ASSETS = "real_assets"


ASSET_CLASS_LABELS = {
    AssetClass.US_EQUITY: "US Equity",
    AssetClass.INTL_EQUITY: "International Equity",
    AssetClass.FIXED_INCOME: "Fixed Income",
    AssetClass.CASH: "Cash",
    AssetClass.ALTERNATIVES: "Alternatives",
    AssetClass.REAL_ASSETS: "Real Assets",
}


class GoalType(StrEnum):
    RETIREMENT = "retirement"
    EDUCATION = "education"
    HOME = "home"
    LEGACY = "legacy"
    LIFE_EVENT = "life_event"
    CUSTOM = "custom"


class ApprovalStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


TERMINAL_APPROVAL_STATUSES = {
    ApprovalStatus.REJECTED,
    ApprovalStatus.CANCELLED,
    ApprovalStatus.COMPLETED,
}

# The single source of truth for the reusable approval engine (§37).
APPROVAL_TRANSITIONS: dict[str, set[str]] = {
    ApprovalStatus.DRAFT: {ApprovalStatus.SUBMITTED, ApprovalStatus.CANCELLED},
    ApprovalStatus.SUBMITTED: {ApprovalStatus.UNDER_REVIEW, ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED},
    ApprovalStatus.UNDER_REVIEW: {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED},
    ApprovalStatus.APPROVED: {ApprovalStatus.COMPLETED, ApprovalStatus.CANCELLED},
    ApprovalStatus.REJECTED: set(),
    ApprovalStatus.CANCELLED: set(),
    ApprovalStatus.COMPLETED: set(),
}


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataFreshness(StrEnum):
    """§39 - never silently present stale information as current."""

    FRESH = "fresh"
    DELAYED = "delayed"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class DocumentCategory(StrEnum):
    TAX = "tax"
    ESTATE = "estate"
    INVESTMENT = "investment"
    INSURANCE = "insurance"
    BANKING = "banking"
    RETIREMENT = "retirement"
    LEGAL = "legal"
    OTHER = "other"


class ComplianceStatus(StrEnum):
    COMPLETE = "complete"
    AT_RISK = "at_risk"
    PENDING = "pending"
    OVERDUE = "overdue"


class RebalanceStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class EntityType(StrEnum):
    ACCOUNT = "account"
    APPROVAL = "approval"
    BENEFICIARY = "beneficiary"
    CLIENT = "client"
    COMPLIANCE_TEST = "compliance_test"
    DISTRIBUTION = "distribution_request"
    DOCUMENT = "document"
    GOAL = "goal"
    HARVEST = "harvest"
    MEETING = "meeting"
    MESSAGE = "message"
    PLAN = "plan"
    PORTFOLIO = "portfolio"
    REBALANCE = "rebalance"
    RECOMMENDATION = "recommendation"
    REPORT = "report"
    SESSION = "session"
    USER = "user"
