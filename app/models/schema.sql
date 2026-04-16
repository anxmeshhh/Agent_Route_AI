-- ============================================================
-- Predictive Delay & Risk Intelligence Agent — MySQL Schema
-- v2.0 — Organisation-based multi-tenant auth added
-- ============================================================

CREATE DATABASE IF NOT EXISTS shipment_risk_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE shipment_risk_db;

-- ── Organisations ─────────────────────────────────────────────
-- Every company / client is an organisation (multi-tenant root)
CREATE TABLE IF NOT EXISTS organisations (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(128) NOT NULL UNIQUE,
    slug         VARCHAR(64)  NOT NULL UNIQUE,   -- URL-safe identifier
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Default org for legacy/unauthenticated shipments
INSERT IGNORE INTO organisations (id, name, slug) VALUES (1, 'Default Organisation', 'default');

-- ── Users ─────────────────────────────────────────────────────
-- One user belongs to exactly one organisation
CREATE TABLE IF NOT EXISTS users (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    org_id          INT UNSIGNED NOT NULL,
    display_name    VARCHAR(128) NOT NULL,
    email_enc       VARBINARY(512) NOT NULL,      -- Fernet (AES-256) encrypted — PII
    email_hash      VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 for lookup (never exposed)
    password_hash   VARCHAR(256) NOT NULL,         -- bcrypt
    role            ENUM('member','admin') DEFAULT 'member',
    is_active       TINYINT(1) DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organisations(id) ON DELETE CASCADE,
    INDEX idx_email_hash (email_hash),
    INDEX idx_org        (org_id)
) ENGINE=InnoDB;

-- ── MFA OTP codes ─────────────────────────────────────────────
-- 6-digit codes with 5-min TTL for two-factor auth
CREATE TABLE IF NOT EXISTS mfa_otp (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    otp_code    VARCHAR(6) NOT NULL,
    expires_at  DATETIME NOT NULL,
    used        TINYINT(1) DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user (user_id)
) ENGINE=InnoDB;

-- ── Refresh Tokens ────────────────────────────────────────────
-- JWT refresh tokens stored as SHA-256 hashes (7-day TTL)
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     INT UNSIGNED NOT NULL,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,
    expires_at  DATETIME NOT NULL,
    revoked     TINYINT(1) DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user  (user_id),
    INDEX idx_token (token_hash)
) ENGINE=InnoDB;

-- ── Org Visibility Requests ───────────────────────────────────
-- Cross-org data sharing: org A requests to see org B's analyses
CREATE TABLE IF NOT EXISTS org_visibility_requests (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    requester_org_id INT UNSIGNED NOT NULL,
    target_org_id    INT UNSIGNED NOT NULL,
    status           ENUM('pending','approved','rejected') DEFAULT 'pending',
    reviewed_by      INT UNSIGNED,                -- admin user id who reviewed
    reviewed_at      DATETIME,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_org_pair (requester_org_id, target_org_id),
    FOREIGN KEY (requester_org_id) REFERENCES organisations(id) ON DELETE CASCADE,
    FOREIGN KEY (target_org_id)   REFERENCES organisations(id) ON DELETE CASCADE,
    INDEX idx_target (target_org_id),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- ── Shipments ────────────────────────────────────────────────
-- Each row is one user query / analysis session
CREATE TABLE IF NOT EXISTS shipments (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    org_id          INT UNSIGNED DEFAULT 1,
    session_id      VARCHAR(36) NOT NULL UNIQUE,
    query_text      TEXT NOT NULL,
    port            VARCHAR(128),
    port_city       VARCHAR(128),
    eta_days        TINYINT UNSIGNED,
    cargo_type      VARCHAR(128),
    vessel_name     VARCHAR(128),
    origin_port     VARCHAR(128),
    status          ENUM('pending','running','completed','failed') DEFAULT 'pending',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (org_id) REFERENCES organisations(id),
    INDEX idx_port      (port),
    INDEX idx_status    (status),
    INDEX idx_created   (created_at),
    INDEX idx_org       (org_id)
) ENGINE=InnoDB;

-- ── Risk Assessments ─────────────────────────────────────────
-- Final output produced by Module 5 (Brain + Groq)
CREATE TABLE IF NOT EXISTS risk_assessments (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    shipment_id     INT UNSIGNED NOT NULL,
    session_id      VARCHAR(36) NOT NULL,
    risk_score      TINYINT UNSIGNED,              -- 0-100
    risk_level      ENUM('LOW','MEDIUM','HIGH','CRITICAL'),
    delay_probability DECIMAL(5,2),               -- percentage
    weather_score   TINYINT UNSIGNED,             -- weather sub-score 0-35
    news_score      TINYINT UNSIGNED,             -- news sub-score 0-35
    historical_score TINYINT UNSIGNED,            -- historical sub-score 0-30
    factors_json    JSON,                         -- array of risk factors
    mitigation_json JSON,                         -- array of strategies
    llm_reasoning   TEXT,                         -- Groq explanation
    llm_model       VARCHAR(64),
    llm_tokens_used INT UNSIGNED,
    confidence_score DECIMAL(4,3),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
    INDEX idx_session   (session_id),
    INDEX idx_score     (risk_score),
    INDEX idx_created   (created_at)
) ENGINE=InnoDB;

-- ── Agent Logs ───────────────────────────────────────────────
-- Every agent action is logged — streamed live to UI for transparency
CREATE TABLE IF NOT EXISTS agent_logs (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id  VARCHAR(36) NOT NULL,
    agent_name  VARCHAR(32) NOT NULL,
    action      VARCHAR(256) NOT NULL,
    status      VARCHAR(16) NOT NULL DEFAULT 'started',
    message     TEXT,
    data_json   JSON,
    duration_ms INT UNSIGNED,
    created_at  DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_session   (session_id),
    INDEX idx_agent     (agent_name),
    INDEX idx_created   (created_at)
) ENGINE=InnoDB;

-- ── Weather Cache ────────────────────────────────────────────
-- TTL: 1 hour — avoids hammering OpenWeather API
CREATE TABLE IF NOT EXISTS weather_cache (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    port_city   VARCHAR(128) NOT NULL,
    data_json   JSON NOT NULL,
    wind_speed  DECIMAL(6,2),                     -- m/s
    conditions  VARCHAR(128),
    temperature DECIMAL(5,2),
    visibility  INT,
    fetched_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL,                -- fetched_at + 1 hour
    UNIQUE KEY uk_port_city (port_city),
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB;

-- ── News Cache ───────────────────────────────────────────────
-- TTL: 6 hours — NewsAPI has 100 calls/day limit on free tier
CREATE TABLE IF NOT EXISTS news_cache (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cache_key   VARCHAR(256) NOT NULL,            -- md5 of query params
    port_city   VARCHAR(128) NOT NULL,
    articles_json JSON NOT NULL,
    article_count TINYINT UNSIGNED,
    fetched_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL,                -- fetched_at + 6 hours
    UNIQUE KEY uk_cache_key (cache_key),
    INDEX idx_port_city (port_city),
    INDEX idx_expires   (expires_at)
) ENGINE=InnoDB;

-- ── Historical Shipments ─────────────────────────────────────
-- Seeded by seed_data.py — used by Module 4 without LLM
CREATE TABLE IF NOT EXISTS historical_shipments (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    port            VARCHAR(128) NOT NULL,
    origin_port     VARCHAR(128),
    cargo_type      VARCHAR(128),
    scheduled_date  DATE NOT NULL,
    actual_date     DATE,
    delay_days      TINYINT,                     -- negative = early
    delay_reason    VARCHAR(256),
    season          ENUM('spring','summer','autumn','winter'),
    year            SMALLINT UNSIGNED,
    month           TINYINT UNSIGNED,
    INDEX idx_port      (port),
    INDEX idx_month     (month),
    INDEX idx_year      (year),
    INDEX idx_port_month (port, month)
) ENGINE=InnoDB;

-- ── Analysis Memory ──────────────────────────────────────────
-- Stores past analyses for institutional learning and recall
CREATE TABLE IF NOT EXISTS analysis_memory (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL,
    port            VARCHAR(128),
    cargo_type      VARCHAR(128),
    risk_score      TINYINT UNSIGNED,
    risk_level      VARCHAR(16),
    factors_summary JSON,
    fingerprint     VARCHAR(32),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_port      (port),
    INDEX idx_cargo     (cargo_type),
    INDEX idx_session   (session_id),
    INDEX idx_created   (created_at)
) ENGINE=InnoDB;

-- ── Prediction Outcomes ──────────────────────────────────────
-- Track actual outcomes to measure prediction accuracy over time
CREATE TABLE IF NOT EXISTS prediction_outcomes (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id          VARCHAR(36) NOT NULL UNIQUE,
    actual_delay_days   TINYINT,
    actual_issues       TEXT,
    reported_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES shipments(session_id) ON DELETE CASCADE,
    INDEX idx_session   (session_id)
) ENGINE=InnoDB;
