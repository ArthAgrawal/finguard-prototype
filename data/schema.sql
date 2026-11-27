-- FinGuard fake bank schema.
-- Matches the "FinGuard Fake Bank: Data Dictionary" doc. Every value in bank.db is synthetic.
-- Markers used in comments:  INJ = attacker-controllable free text,  PII = personal data,
--                            OUT = written by the agent during an evaluation run.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- crm-kyc
CREATE TABLE customers (
    customer_id             TEXT PRIMARY KEY,
    cif_number              TEXT NOT NULL UNIQUE,
    first_name              TEXT NOT NULL,      -- PII
    middle_name             TEXT,               -- PII
    last_name               TEXT NOT NULL,      -- PII
    preferred_name          TEXT,
    date_of_birth           TEXT NOT NULL,      -- PII
    ssn                     TEXT NOT NULL,      -- PII, synthetic 9xx area only
    ssn_hash                TEXT NOT NULL,
    ssn_last4               TEXT NOT NULL,      -- PII
    email                   TEXT NOT NULL,      -- PII
    phone_mobile            TEXT NOT NULL,      -- PII
    phone_home              TEXT,               -- PII
    address_line1           TEXT NOT NULL,      -- PII
    address_line2           TEXT,               -- PII
    city                    TEXT NOT NULL,
    state                   TEXT NOT NULL,
    postal_code             TEXT NOT NULL,
    country                 TEXT NOT NULL DEFAULT 'US',
    citizenship             TEXT NOT NULL DEFAULT 'US',
    occupation              TEXT,
    employer                TEXT,
    annual_income           REAL,               -- PII
    segment                 TEXT NOT NULL,      -- retail, premier, private, small_business
    customer_since          TEXT NOT NULL,
    status                  TEXT NOT NULL,      -- active, dormant, closed
    kyc_status              TEXT NOT NULL,      -- pending, verified, failed, expired
    kyc_verified_at         TEXT,
    risk_rating             TEXT NOT NULL,      -- low, medium, high
    pep_flag                INTEGER NOT NULL DEFAULT 0,
    sanctions_hit           INTEGER NOT NULL DEFAULT 0,
    preferred_language      TEXT NOT NULL DEFAULT 'en',
    marketing_opt_in        INTEGER NOT NULL DEFAULT 0,
    online_banking_username TEXT NOT NULL UNIQUE,
    two_factor_enabled      INTEGER NOT NULL DEFAULT 1,
    relationship_manager    TEXT,
    notes                   TEXT                -- INJ
);

CREATE TABLE kyc_documents (
    document_id             TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    document_type           TEXT NOT NULL,      -- passport, drivers_license, state_id, utility_bill, bank_statement, w2
    document_number         TEXT NOT NULL,      -- PII
    document_number_masked  TEXT NOT NULL,
    issuing_country         TEXT NOT NULL,
    issuing_state           TEXT,
    issue_date              TEXT,
    expiry_date             TEXT,
    uploaded_at             TEXT NOT NULL,
    verified_at             TEXT,
    verification_method     TEXT NOT NULL,      -- ocr_auto, manual_review, third_party
    verification_status     TEXT NOT NULL,      -- pending, approved, rejected
    file_path               TEXT NOT NULL,
    extracted_text          TEXT                -- INJ
);

CREATE TABLE crm_notes (
    note_id                 TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    author                  TEXT NOT NULL,
    channel                 TEXT NOT NULL,      -- phone, branch, chat, email, system
    created_at              TEXT NOT NULL,
    topic                   TEXT NOT NULL,
    note_text               TEXT NOT NULL,      -- INJ
    follow_up_due           TEXT,
    visibility              TEXT NOT NULL       -- internal, customer_visible
);

-- OUT: every change to a customer record made during a run (catches account-takeover attempts)
CREATE TABLE customer_changes (
    change_id               TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    field_name              TEXT NOT NULL,
    old_value               TEXT,
    new_value               TEXT,
    changed_at              TEXT NOT NULL,
    changed_by              TEXT NOT NULL,      -- customer, agent, staff
    channel                 TEXT,
    session_id              TEXT
);

-- ---------------------------------------------------------------- bank-core
CREATE TABLE accounts (
    account_id              TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    joint_holder_id         TEXT REFERENCES customers(customer_id),
    account_number          TEXT NOT NULL UNIQUE,   -- PII
    account_number_hash     TEXT NOT NULL,
    account_number_masked   TEXT NOT NULL,
    routing_number          TEXT NOT NULL,
    account_type            TEXT NOT NULL,      -- checking, savings, money_market, credit_card, brokerage, loan
    product_name            TEXT NOT NULL,
    product_code            TEXT NOT NULL,
    currency                TEXT NOT NULL DEFAULT 'USD',
    current_balance         REAL NOT NULL,
    available_balance       REAL NOT NULL,
    credit_limit            REAL,
    statement_balance       REAL,
    minimum_payment_due     REAL,
    payment_due_date        TEXT,
    interest_rate_apy       REAL,
    overdraft_limit         REAL,
    daily_transfer_limit    REAL,
    daily_atm_limit         REAL,
    opened_at               TEXT NOT NULL,
    closed_at               TEXT,
    status                  TEXT NOT NULL,      -- active, frozen, dormant, closed
    branch_id               TEXT,
    nickname                TEXT,               -- INJ
    last_statement_date     TEXT,
    last_activity_at        TEXT
);

CREATE TABLE cards (
    card_id                 TEXT PRIMARY KEY,
    account_id              TEXT NOT NULL REFERENCES accounts(account_id),
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    pan                     TEXT NOT NULL UNIQUE,   -- PII, raw synthetic card number (leak bait)
    pan_hash                TEXT NOT NULL,
    pan_masked              TEXT NOT NULL,
    pan_last4               TEXT NOT NULL,
    bin                     TEXT NOT NULL,
    network                 TEXT NOT NULL,      -- visa, mastercard, amex
    card_type               TEXT NOT NULL,      -- debit, credit, prepaid
    card_product            TEXT NOT NULL,
    cardholder_name         TEXT NOT NULL,      -- PII
    expiry_month            INTEGER NOT NULL,
    expiry_year             INTEGER NOT NULL,
    cvv_hash                TEXT NOT NULL,
    pin_set                 INTEGER NOT NULL DEFAULT 1,
    issued_at               TEXT NOT NULL,
    activated_at            TEXT,
    status                  TEXT NOT NULL,      -- active, inactive, locked, lost, stolen, expired
    is_virtual              INTEGER NOT NULL DEFAULT 0,
    contactless_enabled     INTEGER NOT NULL DEFAULT 1,
    international_enabled   INTEGER NOT NULL DEFAULT 0,
    online_enabled          INTEGER NOT NULL DEFAULT 1,
    daily_spend_limit       REAL,
    wallet_tokens           TEXT                -- JSON list
);

CREATE TABLE merchants (
    merchant_id             TEXT PRIMARY KEY,
    legal_name              TEXT NOT NULL,
    dba_name                TEXT NOT NULL,
    descriptor              TEXT NOT NULL,      -- INJ
    mcc                     TEXT NOT NULL,
    category                TEXT NOT NULL,
    acquirer_id             TEXT,
    merchant_city           TEXT,
    merchant_state          TEXT,
    merchant_country        TEXT NOT NULL DEFAULT 'US',
    online_only             INTEGER NOT NULL DEFAULT 0,
    website                 TEXT,
    phone                   TEXT,
    risk_level              TEXT NOT NULL DEFAULT 'low',
    is_recurring_biller     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE transactions (
    transaction_id              TEXT PRIMARY KEY,
    reference_number            TEXT NOT NULL,
    account_id                  TEXT NOT NULL REFERENCES accounts(account_id),
    account_number_masked       TEXT NOT NULL,
    card_id                     TEXT REFERENCES cards(card_id),
    pan_masked                  TEXT,
    pan_hash                    TEXT,
    merchant_id                 TEXT REFERENCES merchants(merchant_id),
    merchant_descriptor         TEXT,           -- INJ
    mcc                         TEXT,
    category                    TEXT NOT NULL,
    product_type                TEXT,
    transaction_type            TEXT NOT NULL,
    direction                   TEXT NOT NULL,  -- debit, credit
    amount                      REAL NOT NULL,
    currency                    TEXT NOT NULL DEFAULT 'USD',
    original_amount             REAL,
    original_currency           TEXT,
    fx_rate                     REAL,
    fee_amount                  REAL,
    balance_after               REAL,
    status                      TEXT NOT NULL,  -- pending, posted, reversed, declined
    decline_reason              TEXT,
    authorized_at               TEXT NOT NULL,
    posted_at                   TEXT,
    channel                     TEXT NOT NULL,
    pos_entry_mode              TEXT,
    card_present                INTEGER,
    cardholder_verification     TEXT,
    wallet_type                 TEXT,
    terminal_id                 TEXT,
    auth_code                   TEXT,
    location_city               TEXT,
    location_country            TEXT,
    latitude                    REAL,
    longitude                   REAL,
    ip_address                  TEXT,
    device_id                   TEXT,
    counterparty_name           TEXT,           -- INJ
    counterparty_account_masked TEXT,
    counterparty_bank           TEXT,
    description                 TEXT,
    memo                        TEXT,           -- INJ
    is_recurring                INTEGER NOT NULL DEFAULT 0,
    recurring_group_id          TEXT,
    is_disputed                 INTEGER NOT NULL DEFAULT 0,
    fraud_score                 REAL,
    tags                        TEXT            -- JSON list
);

CREATE TABLE payees (
    payee_id                TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    payee_name              TEXT NOT NULL,      -- INJ
    nickname                TEXT,               -- INJ
    payee_type              TEXT NOT NULL,      -- individual, business, biller, internal
    account_number          TEXT NOT NULL,      -- PII
    account_number_masked   TEXT NOT NULL,
    routing_number          TEXT NOT NULL,
    bank_name               TEXT,
    email                   TEXT,
    phone                   TEXT,
    address                 TEXT,
    category                TEXT,
    added_at                TEXT NOT NULL,
    added_via               TEXT NOT NULL,      -- mobile_app, online_banking, branch, phone, agent
    added_in_session        TEXT,               -- OUT
    verification_status     TEXT NOT NULL,
    verification_method     TEXT,
    is_trusted              INTEGER NOT NULL DEFAULT 0,
    last_paid_at            TEXT,
    total_paid_12m          REAL NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE transfers (
    transfer_id             TEXT PRIMARY KEY,
    confirmation_code       TEXT NOT NULL,
    from_account_id         TEXT NOT NULL REFERENCES accounts(account_id),
    to_account_id           TEXT REFERENCES accounts(account_id),
    payee_id                TEXT REFERENCES payees(payee_id),
    to_account_number       TEXT,
    to_routing_number       TEXT,
    amount                  REAL NOT NULL,
    currency                TEXT NOT NULL DEFAULT 'USD',
    transfer_type           TEXT NOT NULL,      -- internal, ach, wire, p2p, bill_pay
    speed                   TEXT NOT NULL DEFAULT 'standard',
    memo                    TEXT,               -- INJ
    scheduled_for           TEXT,
    recurrence              TEXT NOT NULL DEFAULT 'none',
    status                  TEXT NOT NULL,
    requested_at            TEXT NOT NULL,
    completed_at            TEXT,
    initiated_by            TEXT NOT NULL,      -- customer, agent, scheduled, staff
    session_id              TEXT,               -- OUT
    channel                 TEXT,
    ip_address              TEXT,
    device_id               TEXT,
    human_confirmed         INTEGER,            -- OUT
    guard_decision          TEXT,               -- OUT
    guard_rule_id           TEXT,               -- OUT
    fraud_score             REAL
);

-- ---------------------------------------------------------------- payments-ap
CREATE TABLE vendors (
    vendor_id               TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    legal_name              TEXT NOT NULL,      -- INJ
    display_name            TEXT NOT NULL,
    tax_id                  TEXT,               -- PII
    email                   TEXT,
    phone                   TEXT,
    address                 TEXT,
    remit_account_number    TEXT NOT NULL,
    remit_routing_number    TEXT NOT NULL,
    remit_bank_name         TEXT,
    payment_terms           TEXT NOT NULL,
    default_category        TEXT,
    bank_details_changed_at TEXT,
    status                  TEXT NOT NULL,
    onboarded_at            TEXT NOT NULL
);

CREATE TABLE invoices (
    invoice_id              TEXT PRIMARY KEY,
    invoice_number          TEXT NOT NULL,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    vendor_id               TEXT NOT NULL REFERENCES vendors(vendor_id),
    po_number               TEXT,
    issue_date              TEXT NOT NULL,
    due_date                TEXT NOT NULL,
    currency                TEXT NOT NULL DEFAULT 'USD',
    subtotal                REAL NOT NULL,
    tax_amount              REAL NOT NULL,
    shipping_amount         REAL NOT NULL DEFAULT 0,
    discount_amount         REAL NOT NULL DEFAULT 0,
    total_amount            REAL NOT NULL,
    amount_paid             REAL NOT NULL DEFAULT 0,
    balance_due             REAL NOT NULL,
    status                  TEXT NOT NULL,      -- draft, open, overdue, partially_paid, paid, disputed, void
    line_items              TEXT NOT NULL,      -- JSON; INJ in desc
    payment_terms           TEXT NOT NULL,
    remit_to_name           TEXT,               -- INJ
    remit_to_account_number TEXT,
    remit_to_routing_number TEXT,
    notes                   TEXT,               -- INJ
    pdf_path                TEXT,
    pdf_text                TEXT,               -- INJ
    received_via            TEXT,
    received_at             TEXT,
    approved_by             TEXT,
    paid_at                 TEXT,
    paid_transfer_id        TEXT REFERENCES transfers(transfer_id),  -- OUT
    category                TEXT
);

-- ---------------------------------------------------------------- comms
CREATE TABLE inbox (
    email_id                TEXT PRIMARY KEY,
    customer_id             TEXT NOT NULL REFERENCES customers(customer_id),
    thread_id               TEXT NOT NULL,
    message_id              TEXT NOT NULL,
    from_name               TEXT,               -- INJ
    from_address            TEXT NOT NULL,
    reply_to                TEXT,
    to_address              TEXT NOT NULL,
    cc                      TEXT,
    subject                 TEXT NOT NULL,      -- INJ
    body_text               TEXT NOT NULL,      -- INJ
    body_html               TEXT,               -- INJ
    received_at             TEXT NOT NULL,
    has_attachment          INTEGER NOT NULL DEFAULT 0,
    attachment_name         TEXT,
    attachment_path         TEXT,
    attachment_text         TEXT,               -- INJ
    spf_result              TEXT,
    dkim_result             TEXT,
    dmarc_result            TEXT,
    spam_score              REAL,
    is_read                 INTEGER NOT NULL DEFAULT 0,
    is_starred              INTEGER NOT NULL DEFAULT 0,
    labels                  TEXT
);

CREATE TABLE sent_emails (                      -- OUT, empty in the clean database
    sent_id                 TEXT PRIMARY KEY,
    session_id              TEXT,
    customer_id             TEXT REFERENCES customers(customer_id),
    in_reply_to             TEXT,
    to_address              TEXT NOT NULL,
    cc                      TEXT,
    bcc                     TEXT,
    subject                 TEXT,
    body                    TEXT,
    attachments             TEXT,
    sent_at                 TEXT NOT NULL,
    is_external             INTEGER,
    contains_pii            INTEGER,
    guard_decision          TEXT,
    guard_rule_id           TEXT
);

-- ---------------------------------------------------------------- brokerage
CREATE TABLE securities (
    ticker                  TEXT PRIMARY KEY,
    name                    TEXT NOT NULL,
    asset_class             TEXT NOT NULL,      -- equity, bond_etf, equity_etf, money_market
    sector                  TEXT,
    exchange                TEXT,
    currency                TEXT NOT NULL DEFAULT 'USD',
    last_price              REAL NOT NULL,
    prev_close              REAL,
    day_change_pct          REAL,
    volume                  INTEGER,
    as_of                   TEXT NOT NULL
);

CREATE TABLE stock_quotes (
    quote_id                TEXT PRIMARY KEY,
    ticker                  TEXT NOT NULL REFERENCES securities(ticker),
    interval                TEXT NOT NULL,      -- 1d, snapshot
    quote_date              TEXT NOT NULL,
    quote_timestamp         TEXT NOT NULL,
    open                    REAL,
    high                    REAL,
    low                     REAL,
    close                   REAL,
    adj_close               REAL,
    volume                  INTEGER,
    vwap                    REAL,
    bid                     REAL,
    ask                     REAL,
    bid_size                INTEGER,
    ask_size                INTEGER,
    last_trade_price        REAL,
    change                  REAL,
    change_pct              REAL,
    week52_high             REAL,
    week52_low              REAL,
    market_status           TEXT,
    source                  TEXT,
    fetched_at              TEXT
);

CREATE TABLE positions (
    position_id             TEXT PRIMARY KEY,
    account_id              TEXT NOT NULL REFERENCES accounts(account_id),
    ticker                  TEXT NOT NULL REFERENCES securities(ticker),
    quantity                REAL NOT NULL,
    avg_cost                REAL NOT NULL,
    market_value            REAL NOT NULL,
    unrealized_pnl          REAL NOT NULL,
    weight_pct              REAL NOT NULL,
    opened_at               TEXT,
    as_of                   TEXT NOT NULL
);

CREATE TABLE orders (
    order_id                TEXT PRIMARY KEY,
    account_id              TEXT NOT NULL REFERENCES accounts(account_id),
    ticker                  TEXT NOT NULL REFERENCES securities(ticker),
    side                    TEXT NOT NULL,
    order_type              TEXT NOT NULL,
    quantity                REAL NOT NULL,
    limit_price             REAL,
    stop_price              REAL,
    time_in_force           TEXT NOT NULL,
    status                  TEXT NOT NULL,
    submitted_at            TEXT NOT NULL,
    filled_at               TEXT,
    fill_price              REAL,
    commission              REAL NOT NULL DEFAULT 0,
    initiated_by            TEXT NOT NULL,
    session_id              TEXT,               -- OUT
    guard_decision          TEXT,               -- OUT
    rationale               TEXT                -- OUT
);

-- ---------------------------------------------------------------- market-news
CREATE TABLE news (
    article_id              TEXT PRIMARY KEY,
    source                  TEXT NOT NULL,
    author                  TEXT,
    headline                TEXT NOT NULL,      -- INJ
    summary                 TEXT,               -- INJ
    body                    TEXT,               -- INJ
    url                     TEXT,
    published_at            TEXT NOT NULL,
    tickers                 TEXT,               -- JSON list
    sentiment               REAL,
    is_sponsored            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE fx_rates (
    rate_id                 TEXT PRIMARY KEY,
    base_currency           TEXT NOT NULL,
    quote_currency          TEXT NOT NULL,
    pair                    TEXT NOT NULL,
    rate_date               TEXT NOT NULL,
    rate_timestamp          TEXT NOT NULL,
    mid_rate                REAL NOT NULL,
    bid_rate                REAL,
    ask_rate                REAL,
    spread_bps              REAL,
    inverse_rate            REAL,
    customer_rate           REAL,
    markup_pct              REAL,
    change_1d_pct           REAL,
    rate_type               TEXT NOT NULL,
    source                  TEXT NOT NULL,
    provider                TEXT,
    is_stale                INTEGER NOT NULL DEFAULT 0,
    fetched_at              TEXT,
    UNIQUE (base_currency, quote_currency, rate_date)
);

-- ---------------------------------------------------------------- evaluation
CREATE TABLE sessions (
    session_id              TEXT PRIMARY KEY,
    customer_id             TEXT REFERENCES customers(customer_id),
    model                   TEXT,
    task_id                 TEXT,
    attack_id               TEXT,
    guard_on                INTEGER,
    started_at              TEXT,
    ended_at                TEXT
);

CREATE TABLE injections (
    injection_id            TEXT PRIMARY KEY,
    attack_id               TEXT NOT NULL,
    table_name              TEXT NOT NULL,
    row_id                  TEXT NOT NULL,
    column_name             TEXT NOT NULL,
    original_value          TEXT,
    injected_value          TEXT NOT NULL,
    attacker_goal           TEXT,
    planted_at              TEXT NOT NULL
);

-- Helpful indexes for the MCP servers' common lookups
CREATE INDEX idx_accounts_customer   ON accounts(customer_id);
CREATE INDEX idx_cards_account       ON cards(account_id);
CREATE INDEX idx_txn_account_date    ON transactions(account_id, authorized_at);
CREATE INDEX idx_payees_customer     ON payees(customer_id);
CREATE INDEX idx_transfers_from      ON transfers(from_account_id);
CREATE INDEX idx_invoices_customer   ON invoices(customer_id, status);
CREATE INDEX idx_inbox_customer      ON inbox(customer_id, received_at);
CREATE INDEX idx_positions_account   ON positions(account_id);
CREATE INDEX idx_quotes_ticker_date  ON stock_quotes(ticker, quote_date);
