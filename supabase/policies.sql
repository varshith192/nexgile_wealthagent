-- ===========================================================================
-- Nexgile WealthAgent — row-level security
--
-- WHEN YOU NEED THIS
--
-- The FastAPI service connects with the Supabase service role and enforces
-- authorisation itself, in app/core/deps.py: every request resolves the
-- caller's role, the households they may see, and the permission the route
-- requires. That is the security boundary for the API path, and the service
-- role bypasses RLS by design.
--
-- Enable the policies below if a browser or another client will ever query
-- Supabase directly with the anon key. Defence in depth is cheap here: if the
-- API layer is ever bypassed, the database still refuses to hand a household's
-- data to someone outside it.
--
-- Apply with:
--     psql "$DATABASE_URL" -f supabase/policies.sql
-- ===========================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Identity helpers
--
-- Supabase exposes the signed-in user as auth.uid(). Nexgile users carry the
-- Supabase user id in users.supabase_user_id, which is the join between the
-- two systems.
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS nexgile;

-- The Nexgile user row for the current Supabase session.
CREATE OR REPLACE FUNCTION nexgile.current_user_id()
RETURNS VARCHAR
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, nexgile
AS $$
  SELECT id FROM users WHERE supabase_user_id = auth.uid()::text LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION nexgile.current_role_key()
RETURNS VARCHAR
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, nexgile
AS $$
  SELECT role FROM users WHERE supabase_user_id = auth.uid()::text LIMIT 1;
$$;

-- Roles that see the whole book rather than a single household.
CREATE OR REPLACE FUNCTION nexgile.is_oversight()
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, nexgile
AS $$
  SELECT COALESCE(
    nexgile.current_role_key() IN ('admin', 'compliance', 'operations', 'investment_team'),
    FALSE
  );
$$;

-- Every household the caller may read: their own as a client, plus anything
-- they are assigned to as an advisor.
CREATE OR REPLACE FUNCTION nexgile.accessible_households()
RETURNS TABLE (household_id VARCHAR)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, nexgile
AS $$
  SELECT c.household_id
  FROM clients c
  WHERE c.user_id = nexgile.current_user_id()
  UNION
  SELECT a.household_id
  FROM advisor_assignments a
  WHERE a.advisor_id = nexgile.current_user_id();
$$;

CREATE OR REPLACE FUNCTION nexgile.can_read_household(target VARCHAR)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, nexgile
AS $$
  SELECT nexgile.is_oversight()
      OR target IN (SELECT household_id FROM nexgile.accessible_households());
$$;

-- ---------------------------------------------------------------------------
-- Households and the tables that hang off them
--
-- Read-only policies: writes go through the API, which owns the workflow rules
-- (approval transitions, wash-sale checks, audit events). A direct client
-- write would sidestep all of that, so none is granted.
-- ---------------------------------------------------------------------------

ALTER TABLE households ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS households_read ON households;
CREATE POLICY households_read ON households
  FOR SELECT USING (nexgile.can_read_household(id));

DO $$
DECLARE
  target_table TEXT;
BEGIN
  FOREACH target_table IN ARRAY ARRAY[
    'clients', 'household_members', 'accounts', 'portfolios', 'goals',
    'scenarios', 'recommendations', 'tax_opportunities', 'harvests',
    'estate_plans', 'trusts', 'powers_of_attorney', 'beneficiaries',
    'distribution_requests', 'gifts', 'dafs', 'giving_plans', 'documents',
    'document_requests', 'message_threads', 'meetings', 'rebalances',
    'reports', 'tasks', 'alerts', 'audit_events', 'approvals'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', target_table);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', target_table || '_read', target_table);
    EXECUTE format(
      'CREATE POLICY %I ON %I FOR SELECT USING (nexgile.can_read_household(household_id))',
      target_table || '_read', target_table
    );
  END LOOP;
END
$$;

-- ---------------------------------------------------------------------------
-- Records reached through a parent
-- ---------------------------------------------------------------------------

ALTER TABLE holdings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS holdings_read ON holdings;
CREATE POLICY holdings_read ON holdings
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM accounts a
      WHERE a.id = holdings.account_id AND nexgile.can_read_household(a.household_id)
    )
  );

ALTER TABLE tax_lots ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tax_lots_read ON tax_lots;
CREATE POLICY tax_lots_read ON tax_lots
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM holdings h
      JOIN accounts a ON a.id = h.account_id
      WHERE h.id = tax_lots.holding_id AND nexgile.can_read_household(a.household_id)
    )
  );

ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS transactions_read ON transactions;
CREATE POLICY transactions_read ON transactions
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM accounts a
      WHERE a.id = transactions.account_id AND nexgile.can_read_household(a.household_id)
    )
  );

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS messages_read ON messages;
CREATE POLICY messages_read ON messages
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM message_threads t
      WHERE t.id = messages.thread_id AND nexgile.can_read_household(t.household_id)
    )
  );

ALTER TABLE performance ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS performance_read ON performance;
CREATE POLICY performance_read ON performance
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM portfolios p
      WHERE p.id = performance.portfolio_id AND nexgile.can_read_household(p.household_id)
    )
  );

-- ---------------------------------------------------------------------------
-- The participant's own record
-- ---------------------------------------------------------------------------

ALTER TABLE participants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS participants_read ON participants;
CREATE POLICY participants_read ON participants
  FOR SELECT USING (
    nexgile.is_oversight()
    OR user_id = nexgile.current_user_id()
    OR nexgile.current_role_key() = 'plan_sponsor'
  );

ALTER TABLE contributions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS contributions_read ON contributions;
CREATE POLICY contributions_read ON contributions
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM participants p
      WHERE p.id = contributions.participant_id
        AND (
          nexgile.is_oversight()
          OR p.user_id = nexgile.current_user_id()
          OR nexgile.current_role_key() = 'plan_sponsor'
        )
    )
  );

ALTER TABLE participant_loans ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS participant_loans_read ON participant_loans;
CREATE POLICY participant_loans_read ON participant_loans
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM participants p
      WHERE p.id = participant_loans.participant_id
        AND (nexgile.is_oversight() OR p.user_id = nexgile.current_user_id())
    )
  );

-- ---------------------------------------------------------------------------
-- The caller's own user row
-- ---------------------------------------------------------------------------

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS users_read_self ON users;
CREATE POLICY users_read_self ON users
  FOR SELECT USING (nexgile.is_oversight() OR supabase_user_id = auth.uid()::text);

-- ---------------------------------------------------------------------------
-- Shared reference data
--
-- Securities, benchmarks, custodians, charities, plan lineups and education
-- content contain no household information and are readable by any signed-in
-- user.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  target_table TEXT;
BEGIN
  FOREACH target_table IN ARRAY ARRAY[
    'securities', 'benchmarks', 'custodians', 'charities',
    'education_content', 'roles', 'permissions', 'role_permissions'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', target_table);
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', target_table || '_read', target_table);
    EXECUTE format(
      'CREATE POLICY %I ON %I FOR SELECT USING (auth.uid() IS NOT NULL)',
      target_table || '_read', target_table
    );
  END LOOP;
END
$$;

COMMIT;

-- ---------------------------------------------------------------------------
-- Storage
--
-- Create a private bucket for the document vault. Objects are namespaced by
-- household id, and the API signs every download URL.
--
--   insert into storage.buckets (id, name, public)
--   values ('wealthagent-documents', 'wealthagent-documents', false)
--   on conflict (id) do nothing;
--
--   create policy "documents_read_own_household"
--     on storage.objects for select
--     using (
--       bucket_id = 'wealthagent-documents'
--       and nexgile.can_read_household(split_part(name, '/', 1))
--     );
-- ---------------------------------------------------------------------------
