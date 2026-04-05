-- ============================================================
-- Above Exterior Cleaning — Supabase Schema Migration
-- Run this entire file in the Supabase SQL Editor:
--   supabase.com > your project > SQL Editor > New query > paste > Run
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- ── Customers ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS customers (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    source          text NOT NULL,                      -- 'jobber' | 'quickbooks'
    full_name       text NOT NULL,
    email           text,
    phone           text,
    address_line1   text,
    address_line2   text,
    city            text,
    state           text DEFAULT 'WA',
    zip             text,
    latitude        numeric,
    longitude       numeric,
    created_at      timestamptz,
    updated_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── Jobs ──────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS jobs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    customer_id     uuid REFERENCES customers(id),
    title           text,
    service_type    text,                               -- canonical: roof_cleaning | softwash | pressure_washing | window_cleaning | fence_deck
    status          text,                               -- quote | scheduled | completed | cancelled
    scheduled_start timestamptz,
    scheduled_end   timestamptz,
    completed_at    timestamptz,
    total_amount    numeric(10,2),
    notes           text,
    job_address     text,
    created_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── Quotes ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS quotes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    customer_id     uuid REFERENCES customers(id),
    job_id          uuid REFERENCES jobs(id),
    status          text,                               -- draft | sent | approved | declined
    total_amount    numeric(10,2),
    sent_at         timestamptz,
    approved_at     timestamptz,
    declined_at     timestamptz,
    created_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── Job Line Items ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS job_line_items (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          uuid REFERENCES jobs(id) ON DELETE CASCADE,
    service_type    text,
    description     text,
    quantity        numeric,
    unit_price      numeric(10,2),
    total_price     numeric(10,2)
);


-- ── Invoices ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS invoices (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    source          text NOT NULL,                      -- quickbooks | jobber
    customer_id     uuid REFERENCES customers(id),
    job_id          uuid REFERENCES jobs(id),
    invoice_number  text,
    status          text,                               -- draft | sent | paid | overdue | void
    subtotal        numeric(10,2),
    tax_amount      numeric(10,2),
    total_amount    numeric(10,2),
    amount_paid     numeric(10,2),
    balance_due     numeric(10,2),
    due_date        date,
    paid_date       date,
    created_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── Payments ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS payments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    source          text NOT NULL,
    invoice_id      uuid REFERENCES invoices(id),
    customer_id     uuid REFERENCES customers(id),
    amount          numeric(10,2),
    payment_method  text,                               -- cash | check | card | ach
    payment_date    date,
    reference_number text,
    created_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── Expenses ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS expenses (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    source          text NOT NULL DEFAULT 'quickbooks',
    vendor_name     text,
    category        text,
    description     text,
    amount          numeric(10,2),
    expense_date    date,
    job_id          uuid REFERENCES jobs(id),           -- nullable (job-specific expenses)
    created_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── Ad Campaigns ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ad_campaigns (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    platform        text NOT NULL DEFAULT 'facebook',
    name            text,
    status          text,                               -- ACTIVE | PAUSED | ARCHIVED
    objective       text,
    daily_budget    numeric(10,2),
    lifetime_budget numeric(10,2),
    start_time      timestamptz,
    stop_time       timestamptz,
    created_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── Ad Sets ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ad_sets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    campaign_id     uuid REFERENCES ad_campaigns(id),
    name            text,
    status          text,
    targeting_summary jsonb,
    daily_budget    numeric(10,2),
    bid_strategy    text,
    optimization_goal text,
    start_time      timestamptz,
    stop_time       timestamptz,
    last_synced_at  timestamptz
);


-- ── Ads ───────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    ad_set_id       uuid REFERENCES ad_sets(id),
    campaign_id     uuid REFERENCES ad_campaigns(id),
    name            text,
    status          text,
    creative_type   text,                               -- image | video | carousel
    headline        text,
    body_text       text,
    call_to_action  text,
    last_synced_at  timestamptz
);


-- ── Ad Daily Insights ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ad_insights_daily (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ad_id           uuid REFERENCES ads(id),
    ad_set_id       uuid REFERENCES ad_sets(id),
    campaign_id     uuid REFERENCES ad_campaigns(id),
    date_start      date NOT NULL,
    impressions     integer,
    reach           integer,
    clicks          integer,
    link_clicks     integer,
    spend           numeric(10,2),
    leads           integer,
    cpm             numeric(10,4),
    cpc             numeric(10,4),
    cpl             numeric(10,4),
    ctr             numeric(6,4),
    roas            numeric(10,4),
    raw_json        jsonb,
    last_synced_at  timestamptz,
    UNIQUE (ad_id, date_start)
);


-- ── SMS Conversations ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sms_conversations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    customer_id     uuid REFERENCES customers(id),
    phone_number    text,
    direction       text,                               -- inbound | outbound
    status          text,                               -- open | closed | spam
    last_message_at timestamptz,
    message_count   integer DEFAULT 0,
    created_at      timestamptz,
    last_synced_at  timestamptz
);


-- ── SMS Messages ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sms_messages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    conversation_id uuid REFERENCES sms_conversations(id) ON DELETE CASCADE,
    customer_id     uuid REFERENCES customers(id),
    direction       text,                               -- inbound | outbound
    body            text,
    sent_at         timestamptz,
    delivered_at    timestamptz,
    read_at         timestamptz,
    last_synced_at  timestamptz
);


-- ── Email Threads ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS email_threads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id       text UNIQUE NOT NULL,
    customer_id     uuid REFERENCES customers(id),
    subject         text,
    participants    text[],
    message_count   integer DEFAULT 0,
    last_message_at timestamptz,
    has_unread      boolean DEFAULT false,
    labels          text[],
    last_synced_at  timestamptz
);


-- ── Email Messages ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS email_messages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    thread_id       uuid REFERENCES email_threads(id) ON DELETE CASCADE,
    customer_id     uuid REFERENCES customers(id),
    from_address    text,
    to_addresses    text[],
    subject         text,
    snippet         text,                               -- first 200 chars only
    direction       text,                               -- inbound | outbound
    sent_at         timestamptz,
    labels          text[],
    last_synced_at  timestamptz
);


-- ── Google Reviews ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS google_reviews (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text UNIQUE NOT NULL,
    reviewer_name   text,
    rating          integer CHECK (rating BETWEEN 1 AND 5),
    review_text     text,
    replied         boolean DEFAULT false,
    reply_text      text,
    review_date     date,
    reply_date      date,
    last_synced_at  timestamptz
);


-- ── Google Business Metrics ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS google_business_metrics (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date         date UNIQUE NOT NULL,
    total_reviews       integer,
    average_rating      numeric(3,2),
    searches_direct     integer,
    searches_discovery  integer,
    views_maps          integer,
    views_search        integer,
    calls               integer,
    website_clicks      integer,
    direction_requests  integer,
    last_synced_at      timestamptz
);


-- ── Sync Logs ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sync_logs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source              text NOT NULL,
    sync_type           text NOT NULL DEFAULT 'incremental',
    status              text NOT NULL DEFAULT 'running',
    records_fetched     integer DEFAULT 0,
    records_upserted    integer DEFAULT 0,
    records_failed      integer DEFAULT 0,
    error_message       text,
    started_at          timestamptz DEFAULT now(),
    completed_at        timestamptz,
    duration_seconds    numeric
);


-- ── Indexes ───────────────────────────────────────────────────────────────────

-- Jobs
CREATE INDEX IF NOT EXISTS idx_jobs_customer_id     ON jobs(customer_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status          ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_service_type    ON jobs(service_type);
CREATE INDEX IF NOT EXISTS idx_jobs_completed_at    ON jobs(completed_at);

-- Quotes
CREATE INDEX IF NOT EXISTS idx_quotes_customer_id   ON quotes(customer_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status        ON quotes(status);

-- Invoices
CREATE INDEX IF NOT EXISTS idx_invoices_customer_id ON invoices(customer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_status      ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_paid_date   ON invoices(paid_date);
CREATE INDEX IF NOT EXISTS idx_invoices_job_id      ON invoices(job_id);

-- Payments
CREATE INDEX IF NOT EXISTS idx_payments_customer_id ON payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id  ON payments(invoice_id);

-- Expenses
CREATE INDEX IF NOT EXISTS idx_expenses_expense_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category    ON expenses(category);

-- Ads
CREATE INDEX IF NOT EXISTS idx_ad_insights_date     ON ad_insights_daily(date_start);
CREATE INDEX IF NOT EXISTS idx_ad_insights_campaign ON ad_insights_daily(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_insights_ad_id    ON ad_insights_daily(ad_id);

-- SMS
CREATE INDEX IF NOT EXISTS idx_sms_conv_customer    ON sms_conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_sms_msg_conv         ON sms_messages(conversation_id);

-- Email
CREATE INDEX IF NOT EXISTS idx_email_thread_customer ON email_threads(customer_id);
CREATE INDEX IF NOT EXISTS idx_email_msg_thread     ON email_messages(thread_id);

-- Sync logs
CREATE INDEX IF NOT EXISTS idx_sync_logs_source     ON sync_logs(source);
CREATE INDEX IF NOT EXISTS idx_sync_logs_started    ON sync_logs(started_at);
