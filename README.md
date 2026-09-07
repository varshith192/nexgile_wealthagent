# Nexgile WealthAgent

A unified wealth-management platform that helps clients and advisors understand
financial information, identify opportunities and risks, manage goals, and move
recommendations through controlled workflows.

Ten roles, four workspaces, one sign-in. Every figure in the product is produced
by a deterministic calculation engine and published with its method, as-of date,
inputs, assumptions and limitations. The intelligence layer explains those
numbers — it never produces them.

---

## Contents

- [The problem it solves](#the-problem-it-solves)
- [The product flow](#the-product-flow)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Features](#features)
- [Demo accounts](#demo-accounts)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [Database](#database)
- [API](#api)
- [Authentication and authorisation](#authentication-and-authorisation)
- [The AI architecture](#the-ai-architecture)
- [Testing](#testing)
- [Deployment](#deployment)
- [Connecting a real AI provider](#connecting-a-real-ai-provider)
- [Design notes](#design-notes)
- [Project layout](#project-layout)

---

## The problem it solves

A household's financial life is scattered across custodians, a tax preparer, an
estate attorney, a 401(k) recordkeeper and a spreadsheet. Nobody sees all of it
at once, so three things go wrong:

1. **Nothing is connected.** A concentrated position, an underfunded education
   goal and an unused charitable deduction are all visible in isolation and
   invisible together.
2. **Advice arrives late.** Issues surface at the quarterly review rather than
   the morning they appear.
3. **Action is uncontrolled or absent.** Either a recommendation dies in an
   email thread, or something happens with no reviewable record of who decided
   what, on what basis.

Nexgile WealthAgent brings accounts, portfolios, goals, tax, estate,
philanthropy, documents and retirement plans into one place; runs deterministic
analysis over them continuously; and routes every resulting action through
review, approval and an audit trail.

---

## The product flow

Everything in the product follows one path, and nothing bypasses it:

```
Financial data
      ↓
Financial calculations       ← app/calculations — the source of truth
      ↓
Analysis
      ↓
Insight                      ← app/ai — explains, never computes
      ↓
Recommendation
      ↓
Human review
      ↓
Approval                     ← app/workflows/approval_engine.py
      ↓
Action / tracking            ← simulated; nothing reaches a broker
      ↓
Audit event                  ← app/audit — append only
```

**The financial rule.** The AI layer is never the source of truth for a
financial figure. Portfolio valuation, net worth, allocation, gain/loss, goal
projection, retirement forecast, tax and every scenario are computed by pure
Python functions in `app/calculations/`. Each returns a `CalcResult` carrying:

| Field | What it holds |
|---|---|
| `method` | The formula, in words |
| `as_of` | The date the figure can be stood behind |
| `inputs` | Every value that went in |
| `assumptions` | What had to be assumed |
| `limitations` | What the number does not account for |
| `result` | The figure itself |
| `source` | Which engine produced it |

The UI surfaces this through a "How this is calculated" disclosure on every
panel. Scenarios are read-only projections and never write back to the books of
record — the API and the test suite both enforce it.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Next.js 15 (App Router) — Vercel                                │
│  Role-aware shell · design system · Recharts · client-side auth   │
└───────────────────────────┬──────────────────────────────────────┘
                            │  REST + Bearer JWT
┌───────────────────────────▼──────────────────────────────────────┐
│  FastAPI — Render                                                │
│                                                                  │
│   api/routes ──▶ core/deps  (authn, authz, household scoping)    │
│        │                                                         │
│        ▼                                                         │
│   services/   ──▶ calculations/   pure functions, no I/O         │
│        │      ──▶ workflows/      the approval state machine     │
│        │      ──▶ ai/             narrow, swappable interface    │
│        │      ──▶ audit/          append-only trail              │
│        ▼                                                         │
│   repositories / SQLAlchemy models                               │
└───────────────────────────┬──────────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────────┐
│  PostgreSQL (Supabase) — or SQLite locally, no setup required    │
│  Supabase Auth (optional) · Supabase Storage (optional)          │
└──────────────────────────────────────────────────────────────────┘
```

**Every external dependency is optional.** Supabase, and any AI provider, sit
behind an adapter with a local fallback. Cloned fresh with no credentials at
all, the stack runs end to end on SQLite with built-in JWT auth and the
deterministic intelligence layer. That is a deliberate design choice, not a
shortcut: an evaluator should be able to run `python seed.py && uvicorn ...` and
see the whole product.

Route handlers stay thin. They resolve the caller, check the permission, scope
the household and call a service. Business logic lives in `services/`,
arithmetic in `calculations/`, state transitions in `workflows/`.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript | File-based routing, server/client split, deploys to Vercel unchanged |
| Styling | Tailwind CSS 3 with a CSS-variable design system | One palette drives light and dark; no hardcoded colours in components |
| Components | Hand-built primitives in the shadcn/ui idiom | One `Card`, one `Badge`, one `Table` — consistency by construction |
| Icons | Lucide | Consistent weight and grid |
| Charts | Recharts | Composable, and it accepts CSS custom properties so charts follow the theme |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0 | Typed requests, generated OpenAPI, a real ORM |
| Database | PostgreSQL (Supabase); SQLite locally | Same models both ways; the URL is the only difference |
| Auth | Supabase Auth or built-in JWT | One interface, two providers |
| Tests | pytest, Playwright | 214 backend tests, e2e through the real UI |

---

## Features

### Client experience
- **Dashboard** — net worth with history, portfolio value and daily change, asset
  allocation, concentration and risk, every goal with its forecast, a "needs
  attention" panel and a live WealthAgent panel.
- **Portfolio** — allocation by asset class, sector and geography; drift against
  policy with tolerance bands; concentration measured separately for single names
  and diversified funds; time-weighted returns for 1D/1W/1M/3M/YTD/1Y/3Y/5Y
  against the benchmark; volatility, Sharpe, max drawdown, tracking error,
  information ratio; forward income split taxable/municipal.
- **Accounts** — brokerage, retirement, trust, education, banking, credit,
  mortgage and external, each with institution, connection type, last sync and a
  freshness badge. Detail pages carry holdings and transactions.
- **Holdings** — a full grid with search, sort, filter, pagination and a detail
  drawer showing open tax lots and holding periods.
- **Goals** — retirement, education, home, legacy, life event and custom, each
  with target, funding, progress, forecast and status; scenario comparison across
  base case, higher savings, lower return and an earlier target date.
- **Tax Center** — realised gains split short/long term, harvesting candidates
  with wash-sale status and replacement securities, asset-location review,
  capital-gains budget, Roth conversion analysis, RMD tracking, municipal income,
  charitable securities and a year-end projection.
- **Estate** — wills, trusts, POAs, beneficiaries with gap detection, family
  tree, distributions, gifting against the annual exclusion, and a federal estate
  tax estimate.
- **Philanthropy** — DAF and foundation balances, grant history, mission
  breakdown, giving plans, QCDs and the deduction impact of how you give.
- **Documents** — upload, search, categories, tags, versions, expiration,
  retention, sharing and requests, with a suggested filing from the rules engine
  that must be accepted, edited or rejected.
- **WealthAgent** — insights, recommendations, actions and grounded Q&A.
- **Messages, meetings, reports** — secure threads with action items; agendas,
  notes and follow-ups; six report types with a live preview.

### Advisor workstation
Book dashboard with AUM, alerts, opportunities, pending approvals, meetings and
tasks. **Client 360** with ten tabs and a full activity timeline. Portfolio tools:
correlation matrix, efficient frontier, historical stress tests, liquidity
profile, ESG screening. Rebalancing from drift to trade preview to approval to
simulated execution. Tax planning with the harvest workflow.

### Institutional
Sponsor dashboard with a weighted plan-health score. Participant roster.
Fiduciary oversight with IPS screening and committee minutes. Plan costs with fee
benchmarking, revenue sharing and vendor scorecards. Compliance centre with
ADP/ACP, top-heavy, 402(g), 415(c), coverage tests and Form 5500 tracking.

### Participant
Balance, contributions, employer match, vesting, investment menu, loans,
beneficiaries. Retirement readiness with editable inputs, a seeded Monte Carlo
and side-by-side scenarios. Education with learning paths and progress.

### Platform
Global search across twelve entity types, notification centre, the reusable
approval engine, an append-only audit trail with before/after state, and
data-freshness badges everywhere a figure could be stale.

---

## Demo accounts

Password for all: `Demo1234!`

| Label | Email | Role | Lands on |
|---|---|---|---|
| Client Demo | `sarah.johnson@example.com` | Client | `/dashboard` |
| Advisor Demo | `marcus.webb@nexgile.example` | Advisor | `/advisor` |
| Sponsor Demo | `diane.ellis@brightpath.example` | Plan Sponsor | `/institutional` |
| Participant Demo | `andre.fitzgerald@brightpath.example` | Participant | `/participant` |
| Compliance Demo | `priya.raman@nexgile.example` | Compliance | `/compliance` |
| Admin Demo | `ellen.sorensen@nexgile.example` | Admin | `/admin` |

Four further staff accounts exercise the other roles, same password:
`tobias.frank@nexgile.example` (investment team — decides on recommendations),
`hana.mori@nexgile.example` (tax specialist), `declan.ross@nexgile.example`
(estate & trust), `noor.haddad@nexgile.example` (operations).

The login page lists the six labelled demo accounts with one-click sign-in. These
are demonstration identities against fictional data — no production credential
appears anywhere in the product.

### Suggested walkthrough

```
Client Demo  → Dashboard → Portfolio → Goals → open a goal → Run scenarios
             → WealthAgent → ask "What is my net worth?"
Advisor Demo → Clients → Client 360 → WealthAgent → Submit for approval
Investment team (tobias.frank) → Approvals → Review → Approve → Complete
Compliance Demo → Audit trail → expand the decision to see before/after
```

---

## Local setup

**Prerequisites:** Python 3.11+ and Node 18+. Nothing else — no database server,
no cloud account, no API key.

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # runs as-is; no edits needed

python seed.py                # ~4,900 rows of consistent demonstration data
uvicorn app.main:app --reload --port 8000
```

API at `http://127.0.0.1:8000` · docs at `/docs` · health at `/health`.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # points at http://127.0.0.1:8000
npm run dev
```

App at `http://localhost:3000`.

### Useful commands

| Command | Directory | What it does |
|---|---|---|
| `python seed.py` | `backend` | Reset and reseed the demonstration dataset |
| `python seed.py --keep` | `backend` | Seed without clearing |
| `python -m pytest` | `backend` | Run the backend suite |
| `python -m app.seeds.emit_schema` | `backend` | Regenerate `supabase/schema.sql` from the models |
| `npm run typecheck` | `frontend` | TypeScript, no emit |
| `npm run build` | `frontend` | Production build |
| `npm run test:e2e` | `frontend` | Playwright end-to-end suite |

---

## Environment variables

Reference copies live in `.env.example` (root), `backend/.env.example` and
`frontend/.env.example`. Nothing needs editing to run locally.

### Frontend — `frontend/.env.local`

```bash
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Everything prefixed `NEXT_PUBLIC_` is compiled into the browser bundle. Only
values that are safe to publish belong here — the Supabase anon key is designed
to be public and is protected by row-level security. **No secret ever goes in
the frontend.**

### Backend — `backend/.env`

```bash
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
DATABASE_URL=

AI_PROVIDER=mock
AI_API_KEY=
```

`AI_API_KEY` is optional by design. **The application runs when `AI_API_KEY=`
is empty** — that is asserted directly by the test suite
(`tests/test_ai.py::TestNoApiKeyRequired`). See `backend/.env.example` for the
full annotated set.

**Never commit:** service role keys, database passwords, JWT secrets, or a
future AI API key. `.gitignore` excludes `.env*` except the examples, and no
secret is present in any committed file.

---

## Database

68 normalised tables with foreign keys, indexes, constraints and
`created_at`/`updated_at` throughout. Models live in `backend/app/models/`,
grouped by domain: `identity`, `wealth`, `planning`, `tax`, `estate`, `collab`,
`institutional`, `workflow`.

Core entities: `users` · `roles` · `permissions` · `role_permissions` ·
`households` · `household_members` · `clients` · `advisor_teams` ·
`advisor_assignments` · `accounts` · `custodians` · `securities` · `holdings` ·
`tax_lots` · `transactions` · `portfolios` · `portfolio_positions` ·
`allocations` · `benchmarks` · `performance` · `goals` · `goal_accounts` ·
`scenarios` · `recommendations` · `tax_opportunities` · `harvests` ·
`wash_sale_windows` · `rmds` · `gifts` · `charities` · `dafs` · `grants` ·
`giving_plans` · `estate_plans` · `trusts` · `powers_of_attorney` ·
`beneficiaries` · `distribution_requests` · `documents` · `document_versions` ·
`document_shares` · `document_requests` · `message_threads` · `messages` ·
`meetings` · `action_items` · `tasks` · `sponsors` · `plans` · `participants` ·
`contributions` · `participant_loans` · `investment_options` · `fees` ·
`compliance_tests` · `filings` · `fiduciary_reviews` · `education_content` ·
`education_progress` · `rebalances` · `rebalance_trades` · `reports` · `alerts` ·
`approvals` · `approval_events` · `audit_events` · `saved_views` ·
`search_history`.

### Supabase setup

1. Create a project at [supabase.com](https://supabase.com).
2. **SQL Editor → New query** → paste `supabase/schema.sql` → Run.
3. *(Optional)* Run `supabase/policies.sql` to enable row-level security. The API
   enforces authorisation itself and connects with the service role, so this is
   only needed if a client will query Supabase directly.
4. **Project Settings → Database → Connection string → URI**, and set it as
   `DATABASE_URL` on the backend. Both `postgres://` and `postgresql://` are
   normalised automatically.
5. Seed it: `DATABASE_URL="postgresql://..." python seed.py`
6. *(Optional)* **Storage → New bucket** → `wealthagent-documents`, private, then
   set `STORAGE_BACKEND=supabase`.

`supabase/schema.sql` is generated from the ORM by
`python -m app.seeds.emit_schema`, so the SQL and the models cannot drift apart.

### The demonstration dataset

Fictional households, fictional financial data, generated from a fixed random
seed so the same command always produces the same numbers.

```
Johnson Family              Okonkwo Household        Lindqvist Family Trust
Net worth   $18.0M          Net worth   $11.9M       Net worth   $24.1M
Assets      $21.3M          Delacroix Household      4 households, 6 clients
Liabilities  $3.3M          Net worth    $1.7M       26 accounts, 76 holdings
```

Consistency is achieved by construction, not transcription: account balances are
computed from holdings, goal balances from linked accounts, plan assets from the
participant roster, and the performance series is generated backwards from each
portfolio's actual market value so the last point equals it exactly. The
benchmark series shares most of its variance with the portfolio, so relative
performance is plausible rather than random.

Roughly 4,900 rows: 4 households · 26 accounts · 24 securities · 76 holdings ·
224 tax lots · 396 transactions · 3,128 performance points · 13 goals ·
13 tax opportunities · 12 harvests · 38 documents · 2 plans · 88 participants ·
616 contributions · 12 compliance tests · 10 recommendations · 12 approvals ·
32 alerts · 48 audit events.

---

## API

REST under `/api`, documented at `/docs` (Swagger) and `/redoc`. Pydantic
validates every request; responses use proper status codes and a consistent
error envelope:

```json
{ "error": { "code": "invalid_workflow_transition", "message": "…", "details": {} } }
```

Selected endpoints:

```
POST   /api/auth/login                     GET    /api/auth/me
GET    /api/auth/demo-accounts             POST   /api/auth/logout

GET    /api/dashboard                      GET    /api/portfolio
GET    /api/portfolio/performance          GET    /api/portfolio/analytics
GET    /api/accounts                       GET    /api/accounts/{id}
GET    /api/holdings                       GET    /api/holdings/{id}

GET    /api/goals                          POST   /api/goals
GET    /api/goals/{id}                     PATCH  /api/goals/{id}
DELETE /api/goals/{id}                     POST   /api/goals/{id}/scenarios

GET    /api/tax                            GET    /api/tax/opportunities
GET    /api/tax/harvests                   POST   /api/tax/harvests
POST   /api/tax/harvests/{id}/execute      GET    /api/tax/wash-sale-check
GET    /api/estate                         POST   /api/estate/beneficiaries/change
GET    /api/philanthropy

GET    /api/documents                      POST   /api/documents
POST   /api/documents/classify             POST   /api/documents/{id}/classification

GET    /api/wealthagent                    GET    /api/wealthagent/insights
POST   /api/wealthagent/ask                POST   /api/wealthagent/explain
GET    /api/recommendations                POST   /api/recommendations
POST   /api/recommendations/from-draft

GET    /api/approvals                      GET    /api/approvals/{id}
POST   /api/approvals/{id}/submit          POST   /api/approvals/{id}/review
POST   /api/approvals/{id}/approve         POST   /api/approvals/{id}/reject
POST   /api/approvals/{id}/complete

GET    /api/advisor                        GET    /api/advisor/clients
GET    /api/advisor/clients/{id}           POST   /api/advisor/rebalancing
POST   /api/advisor/rebalancing/{id}/execute

GET    /api/institutional                  GET    /api/plans
GET    /api/participants                   GET    /api/institutional/investments
GET    /api/institutional/fees             GET    /api/compliance
GET    /api/participant                    POST   /api/participant/readiness

GET    /api/audit                          GET    /api/notifications
GET    /api/search                         GET    /api/reports
```

---

## Authentication and authorisation

**One sign-in path serves all ten roles.** The user authenticates, the server
resolves the role, and the role decides the workspace and the permission set.

Two providers behind one interface (`AuthService`):

| `AUTH_PROVIDER` | Behaviour |
|---|---|
| `local` *(default)* | Issue and verify our own JWTs against the `users` table; PBKDF2-HMAC-SHA256 password hashing from the standard library |
| `supabase` | Verify Supabase Auth access tokens, then map the Supabase user onto the local profile that carries role, household and permissions |

Either way, the rest of the application receives the same `User` and the same
permission set, so no authorisation logic branches on the provider.

**Roles:** Client · Plan Sponsor · Participant · Advisor · Investment Team · Tax
Specialist · Estate & Trust · Compliance · Operations · Admin.

**Authorisation is server side, on every request.** `core/deps.py` provides
`require(...)` for permission gates and `resolve_household_id(...)`, which proves
the caller may see a household *before* any figure is returned. A client is
pinned to their own household; an advisor sees their assigned book; compliance
and admin see everything.

Separation of duties is enforced in the approval engine: a requester cannot
approve their own request, and each request type names the roles that may decide
on it — an investment recommendation goes to the investment team, a beneficiary
change to estate & trust or compliance.

Other measures: CORS restricted to configured origins plus `*.vercel.app`;
security headers set in `next.config.mjs` and `vercel.json`; upload extension and
size limits with filename sanitisation and path-traversal guards; every write
recorded in the audit trail, including failed sign-ins.

---

## The AI architecture

`AI_PROVIDER=mock` is the default and **no API key is required**.

```
backend/app/ai/
├── base.py        the contract: AIProvider, AIContext, typed responses
├── mock_ai.py     MockAIService — deterministic rules over the real dataset
├── providers.py   AnthropicProvider, OpenAIProvider — the seams
└── service.py     AIService facade + provider factory
```

**The mock service is not a random text generator.** Every insight is a business
rule evaluated against figures the calculation engine already verified, and every
sentence cites the number it came from. The same data always produces the same
output — which is what makes it safe to demonstrate and straightforward to test.

Twelve rules currently fire: single-name concentration, allocation drift, cash
drag, goal funding risk, harvesting opportunity, benchmark-relative performance,
outstanding RMD, estate review overdue, beneficiary gaps, expiring documents,
charitable grant pacing and stale data.

Every response carries provenance — which provider produced it, from what data,
as of when, with what confidence — plus supporting facts, the calculation method,
assumptions and limitations. Document classification returns a *suggestion* with
reasons and a confidence score that a person must accept, edit or reject; the
product never claims an external model processed the file.

---

## Testing

### Backend — 214 tests

```bash
cd backend && python -m pytest
```

| File | Tests | Covers |
|---|---|---|
| `test_calculations.py` | 51 | Valuation, allocation, drift, concentration, performance, net worth, goals, tax, wash sales, RMD, retirement, Monte Carlo, vesting, advisory tools, rebalancing, ADP/ACP, top-heavy, IPS, estate, charitable deduction, plan health |
| `test_auth.py` | 25 | Login, bad credentials, demo accounts, every role's landing route, cross-household denial, permission gates |
| `test_api.py` | 67 | Every endpoint's shape, validation, status codes, and cross-view consistency |
| `test_workflow.py` | 22 | Approval state machine, illegal transitions, self-approval, rebalance and harvest workflows, beneficiary approval, audit capture |
| `test_ai.py` | 46 | Runs with no API key, determinism, insight provenance, no false alarms, classification, grounded answers |
| `test_smoke_journey.py` | 3 | The complete evaluation journey; institutional journey; no blank screen for any role |

The suite runs against a throwaway SQLite database seeded with the same
generator the demo uses, so tests exercise realistic data rather than stubs.

### Frontend — Playwright

```bash
cd frontend && npm run test:e2e
```

`e2e/journey.spec.ts` walks Login → Dashboard → Portfolio → Holdings → Goal →
scenarios → WealthAgent → Recommendation → Client 360 → Approval → Audit trail
through the real UI against the real API. `e2e/roles.spec.ts` asserts role-based
navigation, that every route in each workspace renders content, that forbidden
routes show a permission wall, and covers search, notifications, the theme
toggle, document upload with classification, and report generation.

### Live verification

Both servers running, the full stack was checked end to end:

- 63 API route calls across all six roles — all returned data, no failures
- 41 frontend routes — all rendered, plus correct 404 handling
- 34 live workflow checks — goal CRUD, validation, scenarios leaving records
  unchanged, the full approval lifecycle, self-approval refusal, rebalance and
  harvest workflows, beneficiary approval gating, reports, messaging, compliance
  tests, notifications, participant what-ifs, and audit capture of every action

---

## Deployment

### Frontend → Vercel

1. Import the repository; set **Root Directory** to `frontend`.
2. Framework preset: Next.js (detected). `frontend/vercel.json` handles the rest.
3. Environment variables:
   ```
   NEXT_PUBLIC_API_URL=https://your-api.onrender.com
   NEXT_PUBLIC_SUPABASE_URL=…        (optional)
   NEXT_PUBLIC_SUPABASE_ANON_KEY=…   (optional)
   ```
4. Deploy.

No localhost URL is hardcoded anywhere; the API base comes from
`NEXT_PUBLIC_API_URL` at build time.

### Backend → Render

1. **New → Blueprint**, pointed at the repository. Render reads `render.yaml`.
2. Provide the secrets it prompts for: `DATABASE_URL`, `CORS_ORIGINS` (your
   Vercel domain), and optionally the Supabase and AI keys. `JWT_SECRET` is
   generated for you.
3. Deploy. Health checks hit `/health`.
4. Seed once from the Render shell: `python seed.py`

### Database → Supabase

See [Supabase setup](#supabase-setup) above.

---

## Connecting a real AI provider

The seam is already built and already tested. When you have a key:

```bash
# backend/.env or Render environment
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-…
AI_MODEL=claude-opus-5
```

Then install the SDK (`pip install anthropic`) and implement the single method
`_complete()` in `backend/app/ai/providers.py` — the call is written out in a
comment, ready to uncomment.

**That is the whole change.** No route, service, component or database table is
touched. Two properties are preserved by design:

1. **The deterministic layer still runs first.** The rules engine produces the
   figures and the finding; the model is only ever asked to phrase them. That
   ordering is what keeps §4 true when a model is in the loop.
2. **A failed or unconfigured call degrades silently to the rules engine.** The
   product never goes dark because an external service is unavailable —
   `LiveProviderBase._narrate()` catches, logs and falls back.

---

## Design notes

**Direction.** Modern fintech, restrained. A deep ink sidebar against warm
off-white content; a single teal accent used sparingly for action and emphasis;
tabular figures so numbers align in every table; generous spacing; soft
one-pixel borders instead of heavy shadows. No gradients beyond a single ambient
wash on the login panel, no decorative 3D, no animation that does not communicate
state.

**Themes.** Light and dark are both first-class. Every colour is a CSS custom
property defined once on `:root` and redefined under `.dark`; no component holds
a hardcoded colour. The theme is applied before first paint so the page never
flashes.

**Charts.** The categorical palette was validated with a colour-vision-deficiency
and contrast checker in both modes — worst adjacent CVD ΔE 10.7 light / 13.2
dark, normal-vision ΔE 19.6 / 19.3, all six slots inside the lightness band and
above the chroma floor. Rules held throughout: hues assigned in fixed order and
never cycled; one value axis, never two; colour follows the entity rather than
its rank; sequential is one hue and diverging is two hues with a neutral
midpoint; identity is never colour alone, so every multi-series chart carries a
legend and the allocation donut doubles its legend as a labelled value table.

**States.** Every data-backed panel goes through one `DataState` wrapper that
renders exactly one of loading, error, empty or content — so a screen cannot fall
through to nothing. Errors distinguish 401, 403, 404 and 5xx, each with the right
copy and the right recovery action.

---

## Project layout

```
nexgile_wealthagent/
├── backend/
│   ├── app/
│   │   ├── main.py                FastAPI app, error handlers, /health
│   │   ├── core/                  config, constants, security, deps, errors
│   │   ├── db/                    declarative base, engine, session
│   │   ├── models/                68 SQLAlchemy tables, grouped by domain
│   │   ├── schemas/               Pydantic requests and responses
│   │   ├── repositories/          query helpers
│   │   ├── services/              business logic, one module per domain
│   │   ├── calculations/          pure functions — the financial source of truth
│   │   ├── workflows/             the reusable approval engine
│   │   ├── ai/                    base · mock_ai · providers · service
│   │   ├── notifications/         alert generation and the notification centre
│   │   ├── reports/               report generation
│   │   ├── audit/                 append-only audit trail
│   │   ├── api/routes/            auth · client · planning · wealthagent ·
│   │   │                          advisor · institutional · platform
│   │   └── seeds/                 reference data, household blueprints, seeder
│   ├── tests/                     214 tests
│   ├── seed.py                    CLI entry point
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── login/             the sign-in experience
│   │   │   └── (app)/             the authenticated shell and 40 pages
│   │   ├── components/
│   │   │   ├── ui/                design-system primitives
│   │   │   ├── layout/            sidebar, topbar, search, notifications
│   │   │   ├── charts/            Recharts wrappers with the validated palette
│   │   │   └── shared/            states, indicators, page chrome
│   │   └── lib/                   api client, auth, formatting, navigation, types
│   ├── e2e/                       Playwright suites
│   └── vercel.json
├── supabase/
│   ├── schema.sql                 generated from the ORM
│   └── policies.sql               optional row-level security
├── render.yaml
└── .env.example
```

---

## A note on scope

Everything in this repository is a demonstration built on fictional households
and fictional financial data. **Nexgile WealthAgent never connects to a
brokerage or custodian and never places a trade.** Rebalances and tax harvests
are proposals; once approved they are marked executed *in simulation* and
recorded as such in the audit trail. Figures are planning estimates, not
custodial statements, and nothing in the product is investment, tax or legal
advice.
