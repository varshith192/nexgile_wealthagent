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
    """Indian account types.

    Deliberately named for what they are in India rather than mapped onto
    foreign equivalents: an EPF account is not an IRA, and the tax treatment,
    withdrawal rules and statutory limits differ in ways the product models.
    """

    DEMAT = "demat"                  # broking account holding listed securities
    MUTUAL_FUND = "mutual_fund"      # folio held directly with an AMC / RTA
    EPF = "epf"                      # Employees Provident Fund
    PPF = "ppf"                      # Public Provident Fund
    NPS = "nps"                      # National Pension System
    SUKANYA = "sukanya"              # Sukanya Samriddhi Account
    HUF = "huf"                      # Hindu Undivided Family
    TRUST = "trust"                  # private family trust
    SAVINGS = "savings"              # savings / current bank account
    FIXED_DEPOSIT = "fixed_deposit"  # bank or corporate FD
    HOME_LOAN = "home_loan"
    CREDIT_CARD = "credit_card"
    EXTERNAL = "external"


ACCOUNT_TYPE_LABELS: dict[str, str] = {
    AccountType.DEMAT: "Demat & Broking",
    AccountType.MUTUAL_FUND: "Mutual Fund Folio",
    AccountType.EPF: "Employees Provident Fund",
    AccountType.PPF: "Public Provident Fund",
    AccountType.NPS: "National Pension System",
    AccountType.SUKANYA: "Sukanya Samriddhi",
    AccountType.HUF: "HUF",
    AccountType.TRUST: "Private Trust",
    AccountType.SAVINGS: "Bank Account",
    AccountType.FIXED_DEPOSIT: "Fixed Deposit",
    AccountType.HOME_LOAN: "Home Loan",
    AccountType.CREDIT_CARD: "Credit Card",
    AccountType.EXTERNAL: "External",
}

LIABILITY_ACCOUNT_TYPES = {AccountType.CREDIT_CARD, AccountType.HOME_LOAN}

# Accounts whose corpus is locked or restricted until a statutory event.
RETIREMENT_ACCOUNT_TYPES = {AccountType.EPF, AccountType.PPF, AccountType.NPS}

# Accounts a nomination is legally required on. In India a nominee is a
# trustee for the legal heirs, not the owner — the product says so explicitly.
NOMINATION_REQUIRED_TYPES = {
    AccountType.EPF,
    AccountType.PPF,
    AccountType.NPS,
    AccountType.SUKANYA,
    AccountType.DEMAT,
    AccountType.MUTUAL_FUND,
}


class TaxTreatment(StrEnum):
    """How a rupee inside the account is taxed on the way out."""

    TAXABLE = "taxable"          # demat, mutual funds, FDs — capital gains apply
    EEE = "eee"                  # PPF, Sukanya — exempt-exempt-exempt
    EET = "eet"                  # NPS — partly taxed at exit
    EPF_EXEMPT = "epf_exempt"    # EPF — exempt after five years continuous service
    NOT_APPLICABLE = "n/a"


TAX_TREATMENT_LABELS: dict[str, str] = {
    TaxTreatment.TAXABLE: "Taxable",
    TaxTreatment.EEE: "Exempt-Exempt-Exempt",
    TaxTreatment.EET: "Exempt-Exempt-Taxed",
    TaxTreatment.EPF_EXEMPT: "Tax-free after 5 years",
    TaxTreatment.NOT_APPLICABLE: "Not applicable",
}


class AssetClass(StrEnum):
    INDIAN_EQUITY = "indian_equity"
    INTL_EQUITY = "intl_equity"
    DEBT = "debt"
    CASH = "cash"
    GOLD = "gold"
    ALTERNATIVES = "alternatives"


ASSET_CLASS_LABELS = {
    AssetClass.INDIAN_EQUITY: "Indian Equity",
    AssetClass.INTL_EQUITY: "International Equity",
    AssetClass.DEBT: "Debt",
    AssetClass.CASH: "Cash & Liquid",
    AssetClass.GOLD: "Gold",
    AssetClass.ALTERNATIVES: "Alternatives & REITs",
}


class TaxRegime(StrEnum):
    """Every Indian taxpayer chooses between two regimes each year."""

    OLD = "old"   # higher rates, but Chapter VI-A deductions available
    NEW = "new"   # lower slab rates, almost no deductions


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
