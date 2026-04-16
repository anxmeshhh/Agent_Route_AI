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
    role            ENUM('user','member','admin') DEFAULT 'user',
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

-- ============================================================
-- REFERENCE TABLES — All agent static data (no hardcoding)
-- ============================================================

-- ── ref_ports — Unified port registry ────────────────────────
CREATE TABLE IF NOT EXISTS ref_ports (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    alias_key        VARCHAR(64) NOT NULL UNIQUE,
    canonical_name   VARCHAR(128) NOT NULL,
    weather_city     VARCHAR(128),
    region           VARCHAR(64),
    capacity_teu     INT UNSIGNED,
    avg_wait_hours   SMALLINT UNSIGNED DEFAULT 18,
    congestion_base  ENUM('LOW','MEDIUM','HIGH') DEFAULT 'MEDIUM',
    labor_risk       ENUM('LOW','MEDIUM','HIGH') DEFAULT 'MEDIUM',
    infrastructure   ENUM('MODERATE','GOOD','EXCELLENT') DEFAULT 'MODERATE',
    efficiency_index DECIMAL(4,2) DEFAULT 0.80,
    peak_months      VARCHAR(32) DEFAULT '[]',
    is_maritime      TINYINT(1) DEFAULT 1,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_ports (alias_key,canonical_name,weather_city,region,capacity_teu,avg_wait_hours,congestion_base,labor_risk,infrastructure,efficiency_index,peak_months,is_maritime) VALUES
('jebel ali','Jebel Ali','Dubai','Middle East',19000000,12,'LOW','LOW','EXCELLENT',0.92,'[10,11,12,1]',1),
('dubai','Jebel Ali','Dubai','Middle East',19000000,12,'LOW','LOW','EXCELLENT',0.92,'[10,11,12,1]',1),
('abu dhabi','Abu Dhabi','Abu Dhabi','Middle East',1000000,14,'LOW','LOW','EXCELLENT',0.88,'[10,11,12]',1),
('hamad','Hamad Port','Doha','Middle East',2000000,10,'LOW','LOW','EXCELLENT',0.89,'[11,12,1]',1),
('doha','Hamad Port','Doha','Middle East',2000000,10,'LOW','LOW','EXCELLENT',0.89,'[11,12,1]',1),
('salalah','Salalah','Salalah','Middle East',5000000,8,'LOW','LOW','EXCELLENT',0.91,'[10,11]',1),
('sohar','Sohar','Sohar','Middle East',1000000,10,'LOW','LOW','GOOD',0.85,'[11,12]',1),
('aden','Aden','Aden','Middle East',500000,24,'HIGH','MEDIUM','MODERATE',0.65,'[10,11]',1),
('singapore','Singapore','Singapore','Southeast Asia',38000000,6,'LOW','LOW','EXCELLENT',0.96,'[10,11,12]',1),
('shanghai','Shanghai','Shanghai','East Asia',47000000,24,'MEDIUM','LOW','EXCELLENT',0.88,'[6,7,8,10,11]',1),
('ningbo','Ningbo','Ningbo','East Asia',35000000,20,'MEDIUM','LOW','EXCELLENT',0.87,'[7,8,10,11]',1),
('shenzhen','Shenzhen','Shenzhen','East Asia',28000000,18,'MEDIUM','LOW','EXCELLENT',0.89,'[6,10,11]',1),
('hong kong','Hong Kong','Hong Kong','East Asia',18000000,18,'MEDIUM','LOW','EXCELLENT',0.90,'[10,11,12]',1),
('guangzhou','Guangzhou','Guangzhou','East Asia',22000000,20,'MEDIUM','LOW','EXCELLENT',0.87,'[6,7,10,11]',1),
('tianjin','Tianjin','Tianjin','East Asia',20000000,22,'MEDIUM','LOW','EXCELLENT',0.85,'[7,8,11]',1),
('busan','Busan','Busan','East Asia',22000000,8,'LOW','LOW','EXCELLENT',0.94,'[7,8,10,11]',1),
('colombo','Colombo','Colombo','South Asia',7200000,14,'MEDIUM','MEDIUM','GOOD',0.82,'[10,11,12,5,6]',1),
('nhava sheva','Nhava Sheva','Mumbai','South Asia',5800000,30,'HIGH','MEDIUM','MODERATE',0.74,'[10,11,12,1]',1),
('kolkata','Kolkata','Kolkata','South Asia',1000000,36,'HIGH','MEDIUM','MODERATE',0.70,'[10,11,12]',1),
('karachi','Karachi','Karachi','South Asia',2500000,28,'HIGH','MEDIUM','MODERATE',0.72,'[10,11]',1),
('klang','Port Klang','Klang','Southeast Asia',14000000,12,'MEDIUM','LOW','GOOD',0.86,'[10,11,12]',1),
('tanjung pelepas','Tanjung Pelepas','Johor Bahru','Southeast Asia',11000000,8,'LOW','LOW','EXCELLENT',0.92,'[10,11]',1),
('rotterdam','Rotterdam','Rotterdam','Europe',14800000,8,'LOW','MEDIUM','EXCELLENT',0.95,'[9,10,11]',1),
('antwerp','Antwerp','Antwerp','Europe',12000000,10,'LOW','MEDIUM','EXCELLENT',0.93,'[9,10,11]',1),
('hamburg','Hamburg','Hamburg','Europe',8700000,10,'LOW','MEDIUM','EXCELLENT',0.91,'[9,10,11]',1),
('felixstowe','Felixstowe','Felixstowe','Europe',4000000,12,'LOW','MEDIUM','GOOD',0.88,'[9,10,11]',1),
('barcelona','Barcelona','Barcelona','Europe',3500000,10,'LOW','LOW','GOOD',0.87,'[7,8,10]',1),
('genoa','Genoa','Genoa','Europe',2000000,12,'LOW','LOW','GOOD',0.85,'[7,8,10]',1),
('piraeus','Piraeus','Athens','Europe',5000000,10,'LOW','MEDIUM','GOOD',0.86,'[9,10,11]',1),
('los angeles','Los Angeles','Los Angeles','North America',9200000,18,'MEDIUM','HIGH','GOOD',0.80,'[8,9,10,11]',1),
('long beach','Long Beach','Long Beach','North America',8000000,18,'MEDIUM','HIGH','GOOD',0.80,'[8,9,10,11]',1),
('new york','New York/New Jersey','New York','North America',7600000,16,'MEDIUM','MEDIUM','GOOD',0.82,'[9,10,11]',1),
('savannah','Savannah','Savannah','North America',5500000,14,'LOW','LOW','GOOD',0.85,'[9,10,11]',1),
('houston','Houston','Houston','North America',3000000,14,'LOW','MEDIUM','GOOD',0.83,'[8,9,10]',1),
('santos','Santos','Santos','South America',4000000,30,'HIGH','MEDIUM','MODERATE',0.72,'[9,10,11]',1),
('callao','Callao','Lima','South America',2000000,20,'MEDIUM','MEDIUM','MODERATE',0.75,'[10,11]',1),
('durban','Durban','Durban','Africa',2800000,24,'MEDIUM','MEDIUM','GOOD',0.78,'[10,11,12]',1),
('mombasa','Mombasa','Mombasa','Africa',1500000,36,'HIGH','MEDIUM','MODERATE',0.70,'[10,11]',1),
('dar es salaam','Dar es Salaam','Dar es Salaam','Africa',800000,40,'HIGH','MEDIUM','MODERATE',0.65,'[10,11]',1),
('casablanca','Casablanca','Casablanca','Africa',1000000,18,'MEDIUM','LOW','GOOD',0.80,'[9,10,11]',1),
('tanger med','Tanger Med','Tangier','Africa',5000000,8,'LOW','LOW','EXCELLENT',0.90,'[9,10,11]',1),
('djibouti','Djibouti','Djibouti','Africa',1500000,20,'MEDIUM','LOW','GOOD',0.78,'[10,11]',1),
('delhi','Delhi','Delhi','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('new delhi','New Delhi','Delhi','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('mumbai','Mumbai','Mumbai','South Asia',5500000,36,'HIGH','MEDIUM','MODERATE',0.72,'[10,11,12,1,2]',1),
('chennai','Chennai','Chennai','South Asia',2000000,24,'MEDIUM','MEDIUM','GOOD',0.78,'[10,11,12]',1),
('bangalore','Bangalore','Bangalore','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('bengaluru','Bangalore','Bangalore','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('hyderabad','Hyderabad','Hyderabad','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('pune','Pune','Pune','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('ahmedabad','Ahmedabad','Ahmedabad','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('jaipur','Jaipur','Jaipur','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('lucknow','Lucknow','Lucknow','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('nagpur','Nagpur','Nagpur','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('surat','Surat','Surat','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('kerala','Thiruvananthapuram','Thiruvananthapuram','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('thiruvananthapuram','Thiruvananthapuram','Thiruvananthapuram','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('trivandrum','Thiruvananthapuram','Thiruvananthapuram','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('kochi','Kochi','Kochi','South Asia',1000000,18,'MEDIUM','LOW','GOOD',0.78,'[10,11]',1),
('cochin','Kochi','Kochi','South Asia',1000000,18,'MEDIUM','LOW','GOOD',0.78,'[10,11]',1),
('coimbatore','Coimbatore','Coimbatore','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('madurai','Madurai','Madurai','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('visakhapatnam','Visakhapatnam','Visakhapatnam','South Asia',1000000,20,'MEDIUM','LOW','MODERATE',0.75,'[10,11]',1),
('bhopal','Bhopal','Bhopal','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('patna','Patna','Patna','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('indore','Indore','Indore','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('chandigarh','Chandigarh','Chandigarh','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('amritsar','Amritsar','Amritsar','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('varanasi','Varanasi','Varanasi','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('guwahati','Guwahati','Guwahati','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('bhubaneswar','Bhubaneswar','Bhubaneswar','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0),
('raipur','Raipur','Raipur','South Asia',NULL,0,'LOW','LOW','MODERATE',0.80,'[]',0);

-- ── ref_cargo_keywords ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_cargo_keywords (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cargo_type VARCHAR(64) NOT NULL,
    keyword    VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_ck (cargo_type, keyword)
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_cargo_keywords (cargo_type, keyword) VALUES
('electronics','electronics'),('electronics','semiconductor'),('electronics','chip'),('electronics','pcb'),('electronics','phones'),('electronics','laptops'),
('perishables','perishable'),('perishables','food'),('perishables','fruit'),('perishables','vegetable'),('perishables','frozen'),('perishables','cold chain'),('perishables','refrigerated'),
('pharmaceutical','pharma'),('pharmaceutical','pharmaceutical'),('pharmaceutical','medicine'),('pharmaceutical','drug'),('pharmaceutical','medical'),('pharmaceutical','vaccine'),
('automotive','automotive'),('automotive','car'),('automotive','vehicle'),('automotive','auto parts'),('automotive','spare parts'),
('chemicals','chemicals'),('chemicals','hazmat'),('chemicals','dangerous goods'),('chemicals','flammable'),('chemicals','toxic'),
('textiles','textiles'),('textiles','apparel'),('textiles','clothing'),('textiles','garments'),('textiles','fabric'),
('machinery','machinery'),('machinery','equipment'),('machinery','heavy equipment'),('machinery','industrial'),
('oil_gas','oil'),('oil_gas','gas'),('oil_gas','petroleum'),('oil_gas','lng'),('oil_gas','crude'),
('general','cargo'),('general','goods'),('general','shipment'),('general','container'),('general','freight');

-- ── ref_chokepoints ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_chokepoints (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    key_name         VARCHAR(64) NOT NULL UNIQUE,
    display_name     VARCHAR(128) NOT NULL,
    search_query     VARCHAR(255) NOT NULL,
    base_score       TINYINT UNSIGNED NOT NULL,
    risk_level       ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL,
    routes_eu_asia   TINYINT(1) DEFAULT 0,
    routes_eu_me     TINYINT(1) DEFAULT 0,
    routes_me_any    TINYINT(1) DEFAULT 0,
    routes_se_asia   TINYINT(1) DEFAULT 0,
    routes_americas  TINYINT(1) DEFAULT 0,
    routes_black_sea TINYINT(1) DEFAULT 0
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_chokepoints (key_name,display_name,search_query,base_score,risk_level,routes_eu_asia,routes_eu_me,routes_me_any,routes_se_asia,routes_americas,routes_black_sea) VALUES
('suez_canal','Suez Canal','Suez Canal shipping disruption closure delay 2025',6,'MEDIUM',1,1,0,0,0,0),
('bab_el_mandeb','Bab el-Mandeb / Red Sea','Red Sea shipping attack Houthi Bab el-Mandeb 2025',14,'HIGH',1,1,0,0,0,0),
('strait_of_hormuz','Strait of Hormuz','Strait of Hormuz Iran tanker shipping risk 2025',10,'HIGH',0,0,1,0,0,0),
('malacca_strait','Strait of Malacca','Strait of Malacca piracy congestion shipping 2025',3,'LOW',0,0,0,1,0,0),
('panama_canal','Panama Canal','Panama Canal drought water level delay restrictions 2025',5,'MEDIUM',0,0,0,0,1,0),
('black_sea','Black Sea','Black Sea shipping Ukraine Russia war mine risk 2025',16,'CRITICAL',0,0,0,0,0,1);

-- ── ref_region_ports ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_region_ports (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    region_key     VARCHAR(64) NOT NULL,
    port_name      VARCHAR(64) NOT NULL,
    is_piracy_zone TINYINT(1) DEFAULT 0,
    risk_level     ENUM('LOW','MEDIUM','HIGH','CRITICAL') DEFAULT 'LOW',
    UNIQUE KEY uq_rp (region_key, port_name)
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_region_ports (region_key,port_name,is_piracy_zone,risk_level) VALUES
('red_sea','aden',1,'HIGH'),('red_sea','djibouti',1,'HIGH'),('red_sea','salalah',1,'HIGH'),
('red_sea','jeddah',1,'HIGH'),('red_sea','port sudan',1,'HIGH'),('red_sea','hudaydah',1,'HIGH'),
('persian_gulf','jebel ali',0,'MEDIUM'),('persian_gulf','dubai',0,'MEDIUM'),('persian_gulf','doha',0,'MEDIUM'),
('persian_gulf','abu dhabi',0,'MEDIUM'),('persian_gulf','bahrain',0,'MEDIUM'),('persian_gulf','kuwait',0,'MEDIUM'),('persian_gulf','muscat',0,'MEDIUM'),
('south_china_sea','ho chi minh',0,'MEDIUM'),('south_china_sea','manila',0,'MEDIUM'),('south_china_sea','singapore',0,'MEDIUM'),('south_china_sea','haiphong',0,'MEDIUM'),
('gulf_guinea','lagos',1,'HIGH'),('gulf_guinea','tema',1,'HIGH'),('gulf_guinea','abidjan',1,'HIGH'),('gulf_guinea','lome',1,'HIGH'),('gulf_guinea','douala',1,'HIGH'),('gulf_guinea','dakar',1,'HIGH'),
('east_africa','mombasa',1,'MEDIUM'),('east_africa','dar es salaam',1,'MEDIUM'),('east_africa','mogadishu',1,'MEDIUM'),('east_africa','maputo',0,'MEDIUM'),
('black_sea_ports','odessa',0,'CRITICAL'),('black_sea_ports','constanta',0,'CRITICAL'),('black_sea_ports','novorossiysk',0,'CRITICAL'),('black_sea_ports','batumi',0,'CRITICAL'),
('europe','rotterdam',0,'LOW'),('europe','hamburg',0,'LOW'),('europe','antwerp',0,'LOW'),('europe','felixstowe',0,'LOW'),('europe','barcelona',0,'LOW'),('europe','genoa',0,'LOW'),('europe','piraeus',0,'LOW'),('europe','le havre',0,'LOW'),
('east_asia','shanghai',0,'LOW'),('east_asia','ningbo',0,'LOW'),('east_asia','shenzhen',0,'LOW'),('east_asia','busan',0,'LOW'),('east_asia','hong kong',0,'LOW'),('east_asia','tianjin',0,'LOW'),('east_asia','qingdao',0,'LOW'),
('se_asia','singapore',0,'LOW'),('se_asia','klang',0,'LOW'),('se_asia','tanjung pelepas',0,'LOW'),('se_asia','colombo',0,'LOW'),('se_asia','jakarta',0,'LOW'),
('south_asia','mumbai',0,'LOW'),('south_asia','nhava sheva',0,'LOW'),('south_asia','chennai',0,'LOW'),('south_asia','kolkata',0,'LOW'),('south_asia','karachi',0,'LOW'),('south_asia','chittagong',0,'LOW'),
('americas','los angeles',0,'LOW'),('americas','long beach',0,'LOW'),('americas','new york',0,'LOW'),('americas','panama',0,'LOW'),('americas','houston',0,'LOW'),('americas','santos',0,'LOW'),('americas','callao',0,'LOW'),
('middle_east','jebel ali',0,'MEDIUM'),('middle_east','dubai',0,'MEDIUM'),('middle_east','doha',0,'MEDIUM'),('middle_east','abu dhabi',0,'MEDIUM'),('middle_east','salalah',0,'MEDIUM'),('middle_east','aden',0,'MEDIUM');

-- ── ref_sanctions ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_sanctions (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    country_name VARCHAR(64) NOT NULL UNIQUE,
    authority    VARCHAR(32) DEFAULT 'OFAC/EU/UN'
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_sanctions (country_name, authority) VALUES
('north korea','OFAC/UN'),('korea (north)','OFAC/UN'),('dprk','OFAC/UN'),
('iran','OFAC/EU/UN'),('iranian','OFAC/EU/UN'),
('syria','OFAC/EU/UN'),('syrian','OFAC/EU/UN'),
('cuba','OFAC'),('cuban','OFAC'),
('crimea','OFAC/EU'),
('russia','OFAC/EU'),('russian','OFAC/EU'),
('belarus','EU'),('belarusian','EU'),
('myanmar','EU/UN'),('burma','EU/UN'),
('venezuela','OFAC'),
('sudan','OFAC/UN'),
('zimbabwe','OFAC/EU');

-- ── ref_route_benchmarks ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_route_benchmarks (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    origin_key      VARCHAR(64) NOT NULL,
    dest_key        VARCHAR(64) NOT NULL,
    via_route       VARCHAR(128),
    normal_days     TINYINT UNSIGNED NOT NULL,
    buffer_days     DECIMAL(4,1) NOT NULL,
    cape_extra_days TINYINT UNSIGNED DEFAULT 14,
    UNIQUE KEY uq_rb (origin_key, dest_key)
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_route_benchmarks (origin_key,dest_key,via_route,normal_days,buffer_days,cape_extra_days) VALUES
('shanghai','rotterdam','Suez',28,3.0,14),
('shanghai','jebel ali','Malacca→Hormuz',14,1.8,14),
('shanghai','los angeles','Transpacific',14,1.5,14),
('singapore','rotterdam','Suez',22,2.5,14),
('singapore','jebel ali','Direct',7,1.0,14),
('singapore','hamburg','Suez',22,2.5,14),
('hamburg','mumbai','Suez',18,2.0,14),
('rotterdam','singapore','Suez',22,2.5,14),
('los angeles','shanghai','Transpacific',14,1.5,14),
('busan','rotterdam','Suez',30,3.0,14),
('mumbai','rotterdam','Suez',17,2.0,14),
('mumbai','jebel ali','Direct',3,0.5,14),
('colombo','rotterdam','Suez',18,2.0,14),
('hong kong','rotterdam','Suez',26,2.8,14),
('busan','los angeles','Transpacific',12,1.5,14),
('antwerp','singapore','Suez',22,2.5,14);

-- ── ref_risk_keywords ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_risk_keywords (
    id       INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    keyword  VARCHAR(64) NOT NULL,
    severity ENUM('HIGH','MEDIUM','LOW') NOT NULL,
    category VARCHAR(32) NOT NULL,
    UNIQUE KEY uq_kw (keyword, category)
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_risk_keywords (keyword, severity, category) VALUES
('attack','HIGH','geo_high'),('missile','HIGH','geo_high'),('closure','HIGH','geo_high'),
('blocked','HIGH','geo_high'),('war','HIGH','geo_high'),('seized','HIGH','geo_high'),
('military','HIGH','geo_high'),('explosion','HIGH','geo_high'),('fire','HIGH','geo_high'),
('sanctions','HIGH','geo_high'),('embargo','HIGH','geo_high'),('conflict','HIGH','geo_high'),
('disruption','MEDIUM','geo_medium'),('delay','MEDIUM','geo_medium'),('restricted','MEDIUM','geo_medium'),
('incident','MEDIUM','geo_medium'),('tension','MEDIUM','geo_medium'),('protest','MEDIUM','geo_medium'),
('drought','MEDIUM','geo_medium'),('congestion','MEDIUM','geo_medium'),('queue','MEDIUM','geo_medium'),('restriction','MEDIUM','geo_medium'),
('strike','HIGH','port_strike'),('labor dispute','HIGH','port_strike'),('walkout','HIGH','port_strike'),
('industrial action','HIGH','port_strike'),('workers protest','HIGH','port_strike'),('dock workers','HIGH','port_strike'),
('closed','HIGH','port_closure'),('closure','HIGH','port_closure'),('operations suspended','HIGH','port_closure'),
('shut down','HIGH','port_closure'),('port shut','HIGH','port_closure'),('blocked entry','HIGH','port_closure'),
('congestion','MEDIUM','port_congestion'),('backlog','MEDIUM','port_congestion'),('queue','MEDIUM','port_congestion'),
('waiting time','MEDIUM','port_congestion'),('dwell time','MEDIUM','port_congestion'),('vessel queue','MEDIUM','port_congestion'),('port delay','MEDIUM','port_congestion'),
('rerouted','HIGH','vessel_reroute'),('diverted','HIGH','vessel_reroute'),('cape of good hope','HIGH','vessel_reroute'),
('new route','HIGH','vessel_reroute'),('avoiding suez','HIGH','vessel_reroute'),('red sea avoid','HIGH','vessel_reroute'),('longer route','HIGH','vessel_reroute'),
('delayed','MEDIUM','vessel_delay'),('behind schedule','MEDIUM','vessel_delay'),('port call','MEDIUM','vessel_delay'),
('anchored waiting','MEDIUM','vessel_delay'),('engine trouble','MEDIUM','vessel_delay'),('mechanical','MEDIUM','vessel_delay'),
('ahead of schedule','LOW','vessel_early'),('early arrival','LOW','vessel_early'),('fast transit','LOW','vessel_early');

-- ── ref_default_origins ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS ref_default_origins (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    dest_keyword   VARCHAR(64) NOT NULL UNIQUE,
    default_origin VARCHAR(64) NOT NULL
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_default_origins (dest_keyword, default_origin) VALUES
('thiruvananthapuram','Delhi'),('kochi','Delhi'),('chennai','Delhi'),
('bangalore','Delhi'),('bengaluru','Delhi'),('hyderabad','Delhi'),
('kolkata','Delhi'),('pune','Delhi'),('ahmedabad','Delhi'),
('mumbai','Delhi'),('kerala','Delhi'),('coimbatore','Delhi'),
('nagpur','Delhi'),('jaipur','Delhi'),('lucknow','Delhi'),
('bhubaneswar','Delhi'),('visakhapatnam','Delhi'),('madurai','Delhi'),
('rotterdam','Shanghai'),('hamburg','Shanghai'),('antwerp','Shanghai'),('felixstowe','Shanghai'),
('los angeles','Shenzhen'),('long beach','Shenzhen'),('seattle','Shenzhen'),
('jebel ali','Singapore'),('dubai','Singapore'),('doha','Singapore');


-- ============================================================
-- ROUTING REFERENCE TABLES (Routes files — no hardcoded values)
-- ============================================================

-- ── ref_geocoords — Universal coordinate registry ─────────────
-- Merges: KNOWN (geocoder), AIRPORTS (air_routing), _CHECKPOINTS (road_routing)
CREATE TABLE IF NOT EXISTS ref_geocoords (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name_key       VARCHAR(128) NOT NULL UNIQUE,
    display        VARCHAR(128) NOT NULL,
    lat            DECIMAL(9,6) NOT NULL,
    lon            DECIMAL(9,6) NOT NULL,
    coord_type     ENUM('city','port','airport','road_hub','chokepoint') NOT NULL DEFAULT 'city',
    iata_code      VARCHAR(4),
    snap_radius_km TINYINT UNSIGNED DEFAULT 35
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_geocoords (name_key,display,lat,lon,coord_type,iata_code,snap_radius_km) VALUES
('delhi','Delhi',28.6139,77.2090,'city',NULL,35),
('new delhi','New Delhi',28.6139,77.2090,'city',NULL,35),
('mumbai','Mumbai',19.0760,72.8777,'city',NULL,35),
('bombay','Mumbai',19.0760,72.8777,'city',NULL,35),
('bangalore','Bangalore',12.9716,77.5946,'city',NULL,35),
('bengaluru','Bangalore',12.9716,77.5946,'city',NULL,35),
('chennai','Chennai',13.0827,80.2707,'city',NULL,35),
('madras','Chennai',13.0827,80.2707,'city',NULL,35),
('kolkata','Kolkata',22.5726,88.3639,'city',NULL,35),
('calcutta','Kolkata',22.5726,88.3639,'city',NULL,35),
('hyderabad','Hyderabad',17.3850,78.4867,'city',NULL,35),
('secunderabad','Secunderabad',17.4399,78.4983,'city',NULL,35),
('pune','Pune',18.5204,73.8567,'city',NULL,35),
('ahmedabad','Ahmedabad',23.0225,72.5714,'city',NULL,35),
('jaipur','Jaipur',26.9124,75.7873,'city',NULL,35),
('lucknow','Lucknow',26.8467,80.9462,'city',NULL,35),
('nagpur','Nagpur',21.1458,79.0882,'city',NULL,35),
('coimbatore','Coimbatore',11.0168,76.9558,'city',NULL,35),
('kochi','Kochi',9.9312,76.2673,'city',NULL,35),
('cochin','Kochi',9.9312,76.2673,'city',NULL,35),
('trivandrum','Thiruvananthapuram',8.5241,76.9366,'city',NULL,35),
('thiruvananthapuram','Thiruvananthapuram',8.5241,76.9366,'city',NULL,35),
('kerala','Kerala (centroid)',10.8505,76.2711,'city',NULL,35),
('indore','Indore',22.7196,75.8577,'city',NULL,35),
('bhopal','Bhopal',23.2599,77.4126,'city',NULL,35),
('surat','Surat',21.1702,72.8311,'city',NULL,35),
('vadodara','Vadodara',22.3072,73.1812,'city',NULL,35),
('baroda','Vadodara',22.3072,73.1812,'city',NULL,35),
('patna','Patna',25.5941,85.1376,'city',NULL,35),
('bhubaneswar','Bhubaneswar',20.2961,85.8245,'city',NULL,35),
('visakhapatnam','Visakhapatnam',17.6868,83.2185,'city',NULL,35),
('vizag','Visakhapatnam',17.6868,83.2185,'city',NULL,35),
('madurai','Madurai',9.9252,78.1198,'city',NULL,35),
('amritsar','Amritsar',31.6340,74.8723,'city',NULL,35),
('chandigarh','Chandigarh',30.7333,76.7794,'city',NULL,35),
('jodhpur','Jodhpur',26.2389,73.0243,'city',NULL,35),
('agra','Agra',27.1767,78.0081,'city',NULL,35),
('varanasi','Varanasi',25.3176,82.9739,'city',NULL,35),
('guwahati','Guwahati',26.1445,91.7362,'city',NULL,35),
('raipur','Raipur',21.2514,81.6296,'city',NULL,35),
('ranchi','Ranchi',23.3441,85.3096,'city',NULL,35),
('dehradun','Dehradun',30.3165,78.0322,'city',NULL,35),
('vijayawada','Vijayawada',16.5062,80.6480,'city',NULL,35),
('mangalore','Mangalore',12.9141,74.8560,'city',NULL,35),
('mysore','Mysore',12.2958,76.6394,'city',NULL,35),
('mysuru','Mysore',12.2958,76.6394,'city',NULL,35),
('tiruchirappalli','Tiruchirappalli',10.7905,78.7047,'city',NULL,35),
('trichy','Tiruchirappalli',10.7905,78.7047,'city',NULL,35),
('nashik','Nashik',19.9975,73.7898,'city',NULL,35),
('aurangabad','Aurangabad',19.8762,75.3433,'city',NULL,35),
('ludhiana','Ludhiana',30.9010,75.8573,'city',NULL,35),
('thirupur','Thirupur',11.1085,77.3411,'city',NULL,35),
('hubli','Hubli',15.3647,75.1240,'city',NULL,35),
('belgaum','Belagavi',15.8497,74.4977,'city',NULL,35),
('belagavi','Belagavi',15.8497,74.4977,'city',NULL,35),
('nhava sheva','Nhava Sheva',18.9500,72.9500,'port',NULL,35),
('mundra','Mundra',22.8393,69.7212,'port',NULL,35),
('shanghai','Shanghai',31.2304,121.4737,'port',NULL,35),
('ningbo','Ningbo',29.8683,121.5440,'port',NULL,35),
('shenzhen','Shenzhen',22.5431,114.0579,'port',NULL,35),
('tianjin','Tianjin',39.3434,117.3616,'port',NULL,35),
('qingdao','Qingdao',36.0671,120.3826,'port',NULL,35),
('guangzhou','Guangzhou',23.1291,113.2644,'port',NULL,35),
('hong kong','Hong Kong',22.3193,114.1694,'port',NULL,35),
('busan','Busan',35.1796,129.0756,'port',NULL,35),
('tokyo','Tokyo',35.6762,139.6503,'city',NULL,35),
('osaka','Osaka',34.6937,135.5023,'city',NULL,35),
('rotterdam','Rotterdam',51.9225,4.4792,'port',NULL,35),
('hamburg','Hamburg',53.5753,10.0153,'port',NULL,35),
('antwerp','Antwerp',51.2608,4.3946,'port',NULL,35),
('felixstowe','Felixstowe',51.9554,1.3519,'port',NULL,35),
('barcelona','Barcelona',41.3874,2.1686,'port',NULL,35),
('genoa','Genoa',44.4056,8.9463,'port',NULL,35),
('marseille','Marseille',43.2965,5.3698,'city',NULL,35),
('piraeus','Piraeus',37.9475,23.6452,'port',NULL,35),
('le havre','Le Havre',49.4944,0.1079,'port',NULL,35),
('singapore','Singapore',1.3521,103.8198,'port',NULL,35),
('jebel ali','Jebel Ali',24.9857,55.0919,'port',NULL,35),
('dubai','Dubai',25.2048,55.2708,'city',NULL,35),
('abu dhabi','Abu Dhabi',24.4539,54.3773,'city',NULL,35),
('salalah','Salalah',17.0239,54.0924,'port',NULL,35),
('colombo','Colombo',6.9271,79.8612,'port',NULL,35),
('los angeles','Los Angeles',33.7701,-118.1937,'port',NULL,35),
('long beach','Long Beach',33.7701,-118.1937,'port',NULL,35),
('new york','New York',40.6643,-74.0000,'port',NULL,35),
('seattle','Seattle',47.6062,-122.3321,'city',NULL,35),
('houston','Houston',29.7604,-95.3698,'city',NULL,35),
('savannah','Savannah',32.0835,-81.0998,'port',NULL,35),
('santos','Santos',-23.9618,-46.3322,'port',NULL,35),
('callao','Callao',-12.0553,-77.1184,'port',NULL,35),
('durban','Durban',-29.8587,31.0218,'port',NULL,35),
('mombasa','Mombasa',-4.0435,39.6682,'port',NULL,35),
('lagos','Lagos',6.5244,3.3792,'city',NULL,35),
('dar es salaam','Dar es Salaam',-6.7924,39.2083,'port',NULL,35),
('sydney','Sydney',-33.8688,151.2093,'city',NULL,35),
('melbourne','Melbourne',-37.8136,144.9631,'city',NULL,35),
('london','London',51.5074,-0.1278,'city',NULL,35),
('paris','Paris',48.8566,2.3522,'city',NULL,35),
('berlin','Berlin',52.5200,13.4050,'city',NULL,35),
('madrid','Madrid',40.4168,-3.7038,'city',NULL,35),
('rome','Rome',41.9028,12.4964,'city',NULL,35),
('milan','Milan',45.4642,9.1900,'city',NULL,35),
('amsterdam','Amsterdam',52.3676,4.9041,'city',NULL,35),
('brussels','Brussels',50.8503,4.3517,'city',NULL,35),
('vienna','Vienna',48.2082,16.3738,'city',NULL,35),
('zurich','Zurich',47.3769,8.5417,'city',NULL,35),
('munich','Munich',48.1351,11.5820,'city',NULL,35),
('frankfurt','Frankfurt',50.1109,8.6821,'city',NULL,35),
('warsaw','Warsaw',52.2297,21.0122,'city',NULL,35),
('prague','Prague',50.0755,14.4378,'city',NULL,35),
('lisbon','Lisbon',38.7223,-9.1393,'city',NULL,35),
('athens','Athens',37.9838,23.7275,'city',NULL,35),
('istanbul','Istanbul',41.0082,28.9784,'city',NULL,35),
('copenhagen','Copenhagen',55.6761,12.5683,'city',NULL,35),
('stockholm','Stockholm',59.3293,18.0686,'city',NULL,35),
('oslo','Oslo',59.9139,10.7522,'city',NULL,35),
('helsinki','Helsinki',60.1699,24.9384,'city',NULL,35),
('budapest','Budapest',47.4979,19.0402,'city',NULL,35),
('bucharest','Bucharest',44.4268,26.1025,'city',NULL,35),
('lyon','Lyon',45.7640,4.8357,'city',NULL,35),
('chicago','Chicago',41.8781,-87.6298,'city',NULL,35),
('san francisco','San Francisco',37.7749,-122.4194,'city',NULL,35),
('miami','Miami',25.7617,-80.1918,'city',NULL,35),
('atlanta','Atlanta',33.7490,-84.3880,'city',NULL,35),
('dallas','Dallas',32.7767,-96.7970,'city',NULL,35),
('denver','Denver',39.7392,-104.9903,'city',NULL,35),
('toronto','Toronto',43.6532,-79.3832,'city',NULL,35),
('vancouver','Vancouver',49.2827,-123.1207,'city',NULL,35),
('montreal','Montreal',45.5017,-73.5673,'city',NULL,35),
('mexico city','Mexico City',19.4326,-99.1332,'city',NULL,35),
('bogota','Bogota',4.7110,-74.0721,'city',NULL,35),
('lima','Lima',-12.0464,-77.0428,'city',NULL,35),
('santiago','Santiago',-33.4489,-70.6693,'city',NULL,35),
('buenos aires','Buenos Aires',-34.6037,-58.3816,'city',NULL,35),
('rio de janeiro','Rio de Janeiro',-22.9068,-43.1729,'city',NULL,35),
('sao paulo','Sao Paulo',-23.5505,-46.6333,'city',NULL,35),
('cairo','Cairo',30.0444,31.2357,'city',NULL,35),
('nairobi','Nairobi',-1.2921,36.8219,'city',NULL,35),
('johannesburg','Johannesburg',-26.2041,28.0473,'city',NULL,35),
('cape town','Cape Town',-33.9249,18.4241,'city',NULL,35),
('casablanca','Casablanca',33.5731,-7.5898,'city',NULL,35),
('riyadh','Riyadh',24.7136,46.6753,'city',NULL,35),
('doha','Doha',25.2854,51.5310,'city',NULL,35),
('tehran','Tehran',35.6892,51.3890,'city',NULL,35),
('ankara','Ankara',39.9334,32.8597,'city',NULL,35),
('addis ababa','Addis Ababa',9.0320,38.7469,'city',NULL,35),
('accra','Accra',5.6037,-0.1870,'city',NULL,35),
('bangkok','Bangkok',13.7563,100.5018,'city',NULL,35),
('kuala lumpur','Kuala Lumpur',3.1390,101.6869,'city',NULL,35),
('jakarta','Jakarta',-6.2088,106.8456,'city',NULL,35),
('manila','Manila',14.5995,120.9842,'city',NULL,35),
('ho chi minh','Ho Chi Minh City',10.8231,106.6297,'city',NULL,35),
('hanoi','Hanoi',21.0285,105.8542,'city',NULL,35),
('seoul','Seoul',37.5665,126.9780,'city',NULL,35),
('beijing','Beijing',39.9042,116.4074,'city',NULL,35),
('taipei','Taipei',25.0330,121.5654,'city',NULL,35),
('brisbane','Brisbane',-27.4698,153.0251,'city',NULL,35),
('perth','Perth',-31.9505,115.8605,'city',NULL,35),
('auckland','Auckland',-36.8485,174.7633,'city',NULL,35),
('del -- indira gandhi intl','DEL — Indira Gandhi Intl',28.5562,77.1000,'airport','DEL',80),
('bom -- chhatrapati shivaji intl','BOM — Chhatrapati Shivaji Intl',19.0896,72.8656,'airport','BOM',80),
('blr -- kempegowda intl','BLR — Kempegowda Intl',13.1986,77.7066,'airport','BLR',80),
('maa -- chennai intl','MAA — Chennai Intl',12.9941,80.1709,'airport','MAA',80),
('ccu -- netaji subhas intl','CCU — Netaji Subhas Intl',22.6547,88.4467,'airport','CCU',80),
('hyd -- rajiv gandhi intl','HYD — Rajiv Gandhi Intl',17.2403,78.4294,'airport','HYD',80),
('cok -- cochin intl','COK — Cochin Intl',10.1520,76.4019,'airport','COK',80),
('amd -- sardar vallabhbhai intl','AMD — Sardar Vallabhbhai Intl',23.0770,72.6347,'airport','AMD',80),
('lhr -- heathrow','LHR — Heathrow',51.4775,-0.4614,'airport','LHR',80),
('cdg -- charles de gaulle','CDG — Charles de Gaulle',49.0097,2.5478,'airport','CDG',80),
('fra -- frankfurt','FRA — Frankfurt',50.0379,8.5622,'airport','FRA',80),
('ams -- schiphol','AMS — Schiphol',52.3086,4.7639,'airport','AMS',80),
('dxb -- dubai intl','DXB — Dubai Intl',25.2532,55.3657,'airport','DXB',80),
('sin -- changi','SIN — Changi',1.3644,103.9915,'airport','SIN',80),
('hkg -- hong kong intl','HKG — Hong Kong Intl',22.3080,113.9185,'airport','HKG',80),
('nrt -- tokyo narita','NRT — Tokyo Narita',35.7720,140.3929,'airport','NRT',80),
('jfk -- john f kennedy','JFK — John F Kennedy',40.6413,-73.7781,'airport','JFK',80),
('ord -- ohare','ORD — OHare',41.9742,-87.9073,'airport','ORD',80),
('lax -- los angeles intl','LAX — Los Angeles Intl',33.9425,-118.4081,'airport','LAX',80),
('syd -- kingsford smith','SYD — Kingsford Smith',-33.9399,151.1753,'airport','SYD',80),
('doh -- doha hamad intl','DOH — Doha Hamad Intl',25.2731,51.6080,'airport','DOH',80),
('ist -- istanbul intl','IST — Istanbul Intl',41.2753,28.7519,'airport','IST',80),
('icn -- incheon','ICN — Incheon',37.4602,126.4407,'airport','ICN',80),
('pek -- beijing capital','PEK — Beijing Capital',40.0799,116.6031,'airport','PEK',80),
('pvg -- shanghai pudong','PVG — Shanghai Pudong',31.1443,121.8083,'airport','PVG',80),
('kul -- klia','KUL — KLIA',2.7456,101.7100,'airport','KUL',80),
('gru -- sao paulo guarulhos','GRU — Sao Paulo Guarulhos',-23.4356,-46.4731,'airport','GRU',80),
('jnb -- or tambo','JNB — OR Tambo',-26.1367,28.2411,'airport','JNB',80),
('nbo -- nairobi jomo kenyatta','NBO — Nairobi Jomo Kenyatta',-1.3192,36.9275,'airport','NBO',80),
('nagpur junction','Nagpur Junction',21.1458,79.0882,'road_hub',NULL,35),
('hyderabad hub','Hyderabad Hub',17.3850,78.4867,'road_hub',NULL,35),
('bengaluru hub','Bengaluru Hub',12.9716,77.5946,'road_hub',NULL,35),
('coimbatore, nh544','Coimbatore, NH544',11.0168,76.9558,'road_hub',NULL,35),
('kochi port','Kochi Port',9.9312,76.2673,'road_hub',NULL,35),
('pune junction','Pune Junction',18.5204,73.8567,'road_hub',NULL,35),
('jaipur hub','Jaipur Hub',26.9124,75.7873,'road_hub',NULL,35),
('ahmedabad hub','Ahmedabad Hub',23.0225,72.5714,'road_hub',NULL,35),
('lucknow hub','Lucknow Hub',26.8467,80.9462,'road_hub',NULL,35),
('surat hub','Surat Hub',21.1702,72.8311,'road_hub',NULL,35),
('vadodara hub','Vadodara Hub',22.3072,73.1812,'road_hub',NULL,35),
('bhopal junction','Bhopal Junction',23.2599,77.4126,'road_hub',NULL,35),
('indore hub','Indore Hub',22.7196,75.8577,'road_hub',NULL,35),
('visakhapatnam hub','Visakhapatnam Hub',17.6868,83.2185,'road_hub',NULL,35),
('bhubaneswar hub','Bhubaneswar Hub',20.2961,85.8245,'road_hub',NULL,35),
('chennai junction','Chennai Junction',13.0827,80.2707,'road_hub',NULL,35),
('kolkata hub','Kolkata Hub',22.5726,88.3639,'road_hub',NULL,35),
('patna hub','Patna Hub',25.5941,85.1376,'road_hub',NULL,35),
('varanasi junction','Varanasi Junction',25.3176,82.9739,'road_hub',NULL,35),
('agra hub','Agra Hub',27.1767,78.0081,'road_hub',NULL,35),
('chandigarh hub','Chandigarh Hub',30.7333,76.7794,'road_hub',NULL,35),
('amritsar hub','Amritsar Hub',31.6340,74.8723,'road_hub',NULL,35),
('madurai hub','Madurai Hub',9.9252,78.1198,'road_hub',NULL,35),
('mangalore hub','Mangalore Hub',12.9141,74.8560,'road_hub',NULL,35),
('mysuru hub','Mysuru Hub',12.2958,76.6394,'road_hub',NULL,35),
('nashik hub','Nashik Hub',19.9975,73.7898,'road_hub',NULL,35),
('hubli junction','Hubli Junction',15.3647,75.1240,'road_hub',NULL,35),
('vijayawada hub','Vijayawada Hub',16.5062,80.6480,'road_hub',NULL,35),
('guwahati hub','Guwahati Hub',26.1445,91.7362,'road_hub',NULL,35),
('ranchi hub','Ranchi Hub',23.3441,85.3096,'road_hub',NULL,35),
('jodhpur hub','Jodhpur Hub',26.2389,73.0243,'road_hub',NULL,35),
('karachi hub','Karachi Hub',24.8607,67.0011,'road_hub',NULL,35),
('lahore hub','Lahore Hub',31.5804,74.3587,'road_hub',NULL,35),
('islamabad hub','Islamabad Hub',33.7294,73.0931,'road_hub',NULL,35),
('colombo hub','Colombo Hub',6.9271,79.8612,'road_hub',NULL,35),
('dhaka hub','Dhaka Hub',23.8103,90.4125,'road_hub',NULL,35),
('kathmandu hub','Kathmandu Hub',27.7172,85.3240,'road_hub',NULL,35),
('bangkok hub','Bangkok Hub',13.7563,100.5018,'road_hub',NULL,35),
('kuala lumpur hub','Kuala Lumpur Hub',3.1390,101.6869,'road_hub',NULL,35),
('jakarta hub','Jakarta Hub',-6.2088,106.8456,'road_hub',NULL,35),
('phnom penh hub','Phnom Penh Hub',11.5564,104.9282,'road_hub',NULL,35),
('ho chi minh hub','Ho Chi Minh Hub',10.8231,106.6297,'road_hub',NULL,35),
('hanoi hub','Hanoi Hub',21.0285,105.8542,'road_hub',NULL,35),
('beijing hub','Beijing Hub',39.9042,116.4074,'road_hub',NULL,35),
('shanghai hub','Shanghai Hub',31.2304,121.4737,'road_hub',NULL,35),
('guangzhou hub','Guangzhou Hub',23.1291,113.2644,'road_hub',NULL,35),
('chengdu hub','Chengdu Hub',30.5728,104.0668,'road_hub',NULL,35),
('wuhan hub','Wuhan Hub',30.5928,114.3055,'road_hub',NULL,35),
('xian hub','Xian Hub',34.3416,108.9398,'road_hub',NULL,35),
('tokyo hub','Tokyo Hub',35.6762,139.6503,'road_hub',NULL,35),
('osaka hub','Osaka Hub',34.6937,135.5023,'road_hub',NULL,35),
('seoul hub','Seoul Hub',37.5665,126.9780,'road_hub',NULL,35),
('paris hub','Paris Hub',48.8566,2.3522,'road_hub',NULL,35),
('berlin hub','Berlin Hub',52.5200,13.4050,'road_hub',NULL,35),
('frankfurt hub','Frankfurt Hub',50.1109,8.6821,'road_hub',NULL,35),
('munich hub','Munich Hub',48.1351,11.5820,'road_hub',NULL,35),
('hamburg hub','Hamburg Hub',53.5753,10.0153,'road_hub',NULL,35),
('london hub','London Hub',51.5074,-0.1278,'road_hub',NULL,35),
('amsterdam hub','Amsterdam Hub',52.3676,4.9041,'road_hub',NULL,35),
('brussels hub','Brussels Hub',50.8503,4.3517,'road_hub',NULL,35),
('milan hub','Milan Hub',45.4642,9.1900,'road_hub',NULL,35),
('rome hub','Rome Hub',41.9028,12.4964,'road_hub',NULL,35),
('madrid hub','Madrid Hub',40.4168,-3.7038,'road_hub',NULL,35),
('barcelona hub','Barcelona Hub',41.3874,2.1686,'road_hub',NULL,35),
('vienna hub','Vienna Hub',48.2082,16.3738,'road_hub',NULL,35),
('warsaw hub','Warsaw Hub',52.2297,21.0122,'road_hub',NULL,35),
('prague hub','Prague Hub',50.0755,14.4378,'road_hub',NULL,35),
('zurich hub','Zurich Hub',47.3769,8.5417,'road_hub',NULL,35),
('lyon hub','Lyon Hub',45.7640,4.8357,'road_hub',NULL,35),
('marseille hub','Marseille Hub',43.2965,5.3698,'road_hub',NULL,35),
('stockholm hub','Stockholm Hub',59.3293,18.0686,'road_hub',NULL,35),
('copenhagen hub','Copenhagen Hub',55.6761,12.5683,'road_hub',NULL,35),
('helsinki hub','Helsinki Hub',60.1699,24.9384,'road_hub',NULL,35),
('oslo hub','Oslo Hub',59.9139,10.7522,'road_hub',NULL,35),
('athens hub','Athens Hub',37.9838,23.7275,'road_hub',NULL,35),
('istanbul hub','Istanbul Hub',41.0082,28.9784,'road_hub',NULL,35),
('bucharest hub','Bucharest Hub',44.4268,26.1025,'road_hub',NULL,35),
('budapest hub','Budapest Hub',47.4979,19.0402,'road_hub',NULL,35),
('dubai hub','Dubai Hub',25.2048,55.2708,'road_hub',NULL,35),
('riyadh hub','Riyadh Hub',24.7136,46.6753,'road_hub',NULL,35),
('tehran hub','Tehran Hub',35.6892,51.3890,'road_hub',NULL,35),
('ankara hub','Ankara Hub',39.9334,32.8597,'road_hub',NULL,35),
('cairo hub','Cairo Hub',30.0444,31.2357,'road_hub',NULL,35),
('casablanca hub','Casablanca Hub',33.5731,-7.5898,'road_hub',NULL,35),
('nairobi hub','Nairobi Hub',-1.2921,36.8219,'road_hub',NULL,35),
('addis ababa hub','Addis Ababa Hub',9.0320,38.7469,'road_hub',NULL,35),
('lagos hub','Lagos Hub',6.5244,3.3792,'road_hub',NULL,35),
('accra hub','Accra Hub',5.6037,-0.1870,'road_hub',NULL,35),
('johannesburg hub','Johannesburg Hub',-26.2041,28.0473,'road_hub',NULL,35),
('cape town hub','Cape Town Hub',-33.9249,18.4241,'road_hub',NULL,35),
('dar es salaam hub','Dar es Salaam Hub',-6.7924,39.2083,'road_hub',NULL,35),
('new york hub','New York Hub',40.7128,-74.0060,'road_hub',NULL,35),
('los angeles hub','Los Angeles Hub',34.0522,-118.2437,'road_hub',NULL,35),
('chicago hub','Chicago Hub',41.8781,-87.6298,'road_hub',NULL,35),
('houston hub','Houston Hub',29.7604,-95.3698,'road_hub',NULL,35),
('miami hub','Miami Hub',25.7617,-80.1918,'road_hub',NULL,35),
('atlanta hub','Atlanta Hub',33.7490,-84.3880,'road_hub',NULL,35),
('dallas hub','Dallas Hub',32.7767,-96.7970,'road_hub',NULL,35),
('toronto hub','Toronto Hub',43.6532,-79.3832,'road_hub',NULL,35),
('montreal hub','Montreal Hub',45.5017,-73.5673,'road_hub',NULL,35),
('mexico city hub','Mexico City Hub',19.4326,-99.1332,'road_hub',NULL,35),
('sao paulo hub','Sao Paulo Hub',-23.5505,-46.6333,'road_hub',NULL,35),
('rio de janeiro hub','Rio de Janeiro Hub',-22.9068,-43.1729,'road_hub',NULL,35),
('buenos aires hub','Buenos Aires Hub',-34.6037,-58.3816,'road_hub',NULL,35),
('santiago hub','Santiago Hub',-33.4489,-70.6693,'road_hub',NULL,35),
('bogota hub','Bogota Hub',4.7110,-74.0721,'road_hub',NULL,35),
('lima hub','Lima Hub',-12.0464,-77.0428,'road_hub',NULL,35),
('sydney hub','Sydney Hub',-33.8688,151.2093,'road_hub',NULL,35),
('melbourne hub','Melbourne Hub',-37.8136,144.9631,'road_hub',NULL,35),
('brisbane hub','Brisbane Hub',-27.4698,153.0251,'road_hub',NULL,35),
('perth hub','Perth Hub',-31.9505,115.8605,'road_hub',NULL,35),
('auckland hub','Auckland Hub',-36.8485,174.7633,'road_hub',NULL,35),
('suez canal cp','Suez Canal',30.0,32.55,'chokepoint',NULL,5),
('bab el-mandeb cp','Bab el-Mandeb',12.65,43.30,'chokepoint',NULL,5),
('strait of gibraltar cp','Strait of Gibraltar',35.95,-5.45,'chokepoint',NULL,5),
('malacca strait cp','Malacca Strait',1.25,103.65,'chokepoint',NULL,5),
('strait of hormuz cp','Strait of Hormuz',26.56,56.25,'chokepoint',NULL,5),
('panama canal cp','Panama Canal',8.99,-79.57,'chokepoint',NULL,5),
('cape of good hope cp','Cape of Good Hope',-34.36,18.47,'chokepoint',NULL,5),
('dover strait cp','Dover Strait',51.11,1.35,'chokepoint',NULL,5),
('south china sea cp','South China Sea',12.0,114.0,'chokepoint',NULL,5),
('arabian sea cp','Arabian Sea',15.0,65.0,'chokepoint',NULL,5),
('eastern mediterranean cp','Eastern Mediterranean',34.0,25.0,'chokepoint',NULL,5),
('north pacific e cp','North Pacific E',35.0,150.0,'chokepoint',NULL,5),
('north pacific w cp','North Pacific W',35.0,-145.0,'chokepoint',NULL,5),
('north atlantic cp','North Atlantic',45.0,-30.0,'chokepoint',NULL,5),
('south atlantic cp','South Atlantic',-15.0,-25.0,'chokepoint',NULL,5);

-- ── ref_maritime_routes — Route table (region pairs -> chokepoint sequences) ─
CREATE TABLE IF NOT EXISTS ref_maritime_routes (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    origin_region    VARCHAR(32) NOT NULL,
    dest_region      VARCHAR(32) NOT NULL,
    chokepoint_keys  JSON NOT NULL,
    UNIQUE KEY uq_mr (origin_region, dest_region)
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_maritime_routes (origin_region, dest_region, chokepoint_keys) VALUES
('east_asia','europe','["south china sea cp","malacca strait cp","arabian sea cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp"]'),
('east_asia','middle_east','["south china sea cp","malacca strait cp","arabian sea cp","strait of hormuz cp"]'),
('east_asia','indian_ocean','["south china sea cp","malacca strait cp"]'),
('east_asia','us_west','["north pacific e cp","north pacific w cp"]'),
('east_asia','us_east','["south china sea cp","malacca strait cp","arabian sea cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp","north atlantic cp"]'),
('east_asia','africa','["south china sea cp","malacca strait cp","arabian sea cp","bab el-mandeb cp"]'),
('east_asia','south_america','["north pacific e cp","north pacific w cp","panama canal cp"]'),
('east_asia','oceania','["south china sea cp"]'),
('indian_ocean','europe','["arabian sea cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp"]'),
('indian_ocean','middle_east','["arabian sea cp","strait of hormuz cp"]'),
('indian_ocean','us_east','["arabian sea cp","bab el-mandeb cp","suez canal cp","strait of gibraltar cp","north atlantic cp"]'),
('indian_ocean','africa','["arabian sea cp","bab el-mandeb cp"]'),
('indian_ocean','east_asia','["malacca strait cp","south china sea cp"]'),
('europe','us_east','["dover strait cp","north atlantic cp"]'),
('europe','us_west','["strait of gibraltar cp","panama canal cp"]'),
('europe','south_america','["strait of gibraltar cp","south atlantic cp"]'),
('europe','middle_east','["strait of gibraltar cp","eastern mediterranean cp","suez canal cp","bab el-mandeb cp","strait of hormuz cp"]'),
('europe','africa','["strait of gibraltar cp"]'),
('europe','indian_ocean','["strait of gibraltar cp","eastern mediterranean cp","suez canal cp","bab el-mandeb cp","arabian sea cp"]'),
('europe','oceania','["strait of gibraltar cp","eastern mediterranean cp","suez canal cp","bab el-mandeb cp","arabian sea cp","malacca strait cp","south china sea cp"]'),
('middle_east','europe','["strait of hormuz cp","bab el-mandeb cp","suez canal cp","eastern mediterranean cp","strait of gibraltar cp"]'),
('middle_east','us_east','["strait of hormuz cp","bab el-mandeb cp","suez canal cp","strait of gibraltar cp","north atlantic cp"]'),
('middle_east','africa','["strait of hormuz cp","bab el-mandeb cp"]'),
('middle_east','east_asia','["strait of hormuz cp","arabian sea cp","malacca strait cp","south china sea cp"]'),
('middle_east','indian_ocean','["strait of hormuz cp","arabian sea cp"]'),
('us_east','south_america','["south atlantic cp"]'),
('us_west','south_america','["panama canal cp"]'),
('us_west','east_asia','["north pacific w cp","north pacific e cp"]'),
('us_east','europe','["north atlantic cp","dover strait cp"]'),
('africa','south_america','["cape of good hope cp","south atlantic cp"]'),
('africa','europe','["strait of gibraltar cp"]'),
('africa','east_asia','["bab el-mandeb cp","arabian sea cp","malacca strait cp","south china sea cp"]'),
('africa','indian_ocean','["bab el-mandeb cp","arabian sea cp"]');

-- ── ref_cost_rates — Daily operating costs per mode + cargo ──────
CREATE TABLE IF NOT EXISTS ref_cost_rates (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    transport_mode ENUM('road','air','sea') NOT NULL,
    cargo_type     VARCHAR(64) NOT NULL,
    daily_cost_usd INT UNSIGNED NOT NULL,
    cost_source    VARCHAR(64) DEFAULT 'Industry estimate',
    UNIQUE KEY uq_cr (transport_mode, cargo_type)
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_cost_rates (transport_mode, cargo_type, daily_cost_usd, cost_source) VALUES
('road','electronics',2000,'IRU 2024 road freight rates'),
('road','perishables',2500,'IRU 2024 road freight rates'),
('road','automotive',1800,'IRU 2024 road freight rates'),
('road','chemicals',2200,'IRU 2024 road freight rates'),
('road','pharmaceutical',2800,'IRU 2024 road freight rates'),
('road','pharmaceuticals',2800,'IRU 2024 road freight rates'),
('road','general',1200,'IRU 2024 road freight rates'),
('road','bulk',1000,'IRU 2024 road freight rates'),
('road','energy',3000,'IRU 2024 road freight rates'),
('air','electronics',12000,'IATA 2024 air cargo rates'),
('air','perishables',15000,'IATA 2024 air cargo rates'),
('air','automotive',8000,'IATA 2024 air cargo rates'),
('air','chemicals',10000,'IATA 2024 air cargo rates'),
('air','pharmaceutical',18000,'IATA 2024 air cargo rates'),
('air','pharmaceuticals',18000,'IATA 2024 air cargo rates'),
('air','general',6000,'IATA 2024 air cargo rates'),
('air','bulk',5000,'IATA 2024 air cargo rates'),
('air','energy',8000,'IATA 2024 air cargo rates'),
('sea','electronics',85000,'BIMCO 2024 charter rates'),
('sea','perishables',72000,'BIMCO 2024 charter rates'),
('sea','automotive',68000,'BIMCO 2024 charter rates'),
('sea','chemicals',75000,'BIMCO 2024 charter rates'),
('sea','pharmaceutical',90000,'BIMCO 2024 charter rates'),
('sea','pharmaceuticals',90000,'BIMCO 2024 charter rates'),
('sea','general',55000,'BIMCO 2024 charter rates'),
('sea','bulk',28000,'BIMCO 2024 charter rates'),
('sea','energy',110000,'BIMCO 2024 charter rates');

-- ── ref_delay_bands — risk score → delay probability mapping ─────
CREATE TABLE IF NOT EXISTS ref_delay_bands (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    risk_score_min      TINYINT UNSIGNED NOT NULL,
    risk_score_max      TINYINT UNSIGNED NOT NULL,
    delay_probability   DECIMAL(4,2) NOT NULL,
    expected_delay_days DECIMAL(4,1) NOT NULL
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_delay_bands (risk_score_min, risk_score_max, delay_probability, expected_delay_days) VALUES
(80, 100, 0.82, 4.5),
(65,  79, 0.65, 3.1),
(45,  64, 0.42, 1.8),
(25,  44, 0.22, 0.9),
(0,   24, 0.10, 0.3);

-- ── ref_chokepoint_intel — AI reasoning for chokepoint waypoints ──
CREATE TABLE IF NOT EXISTS ref_chokepoint_intel (
    id           INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    key_name     VARCHAR(32) NOT NULL UNIQUE,
    why_chosen   TEXT NOT NULL,
    saves        VARCHAR(128),
    risk_notes   VARCHAR(255),
    intel_source VARCHAR(64)
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_chokepoint_intel (key_name, why_chosen, saves, risk_notes, intel_source) VALUES
('suez','Shortest Asia-Europe corridor — avoids 6,000nm Cape of Good Hope detour','12-15 transit days','Canal congestion, Houthi threat in Red Sea approach','IMO maritime advisory'),
('malacca','Shortest Pacific-Indian Ocean passage — 40% of world trade flows here','4-6 transit days vs Lombok Strait','Piracy hotspot, extreme traffic density','ReCAAP ISC'),
('gibraltar','Only viable Atlantic-Mediterranean entry without circumnavigating Africa','10,000+ nm vs Cape route','Strong currents, dense traffic','EMSA routing guidance'),
('hormuz','Only maritime exit from Persian Gulf — mandatory for Gulf-origin cargo','No alternative — geography-locked','Geopolitical tension, military activity','UKMTO advisory'),
('panama','Pacific-Atlantic shortcut — eliminates Cape Horn rounding','8,000nm and 15+ days','Lock capacity limits, drought water-level restrictions','ACP canal authority'),
('cape','Selected because Suez route is higher risk or blocked','Avoids Suez congestion/security risk','Rough seas, +12 days transit time, higher fuel cost','SA maritime authority'),
('bab','Mandatory Red Sea approach for Suez-bound vessels','No alternative for Suez access','Security corridor, Houthi threat zone','UKMTO advisory'),
('dover','North Sea-English Channel link — busiest shipping lane globally','Direct access to NW European ports','Extreme traffic density, fog risk','MCA Dover TSS');

-- ── ref_maritime_alt_routes — Alternate sea route definitions ────
CREATE TABLE IF NOT EXISTS ref_maritime_alt_routes (
    id               INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    trigger_key      VARCHAR(32) NOT NULL UNIQUE,
    via_label        VARCHAR(64) NOT NULL,
    reason           TEXT,
    when_to_choose   TEXT,
    waypoints_json   JSON NOT NULL,
    km_per_day       SMALLINT UNSIGNED DEFAULT 550
) ENGINE=InnoDB;

INSERT IGNORE INTO ref_maritime_alt_routes (trigger_key, via_label, reason, when_to_choose, waypoints_json, km_per_day) VALUES
('suez','Cape of Good Hope','Avoids Red Sea/Suez corridor — eliminates geopolitical risk (Houthi threat, canal congestion)','Choose when Red Sea security is elevated or Suez Canal has queue delays > 48 hours.','[{"lat":-6.0,"lon":71.0,"name":"Indian Ocean (South)"},{"lat":-34.3568,"lon":18.4740,"name":"Cape of Good Hope"},{"lat":-15.0,"lon":-5.0,"name":"South Atlantic"},{"lat":10.0,"lon":-20.0,"name":"Central Atlantic"}]',550),
('bab','Cape of Good Hope','Avoids Red Sea/Suez corridor — eliminates geopolitical risk (Houthi threat, canal congestion)','Choose when Red Sea security is elevated or Suez Canal has queue delays > 48 hours.','[{"lat":-6.0,"lon":71.0,"name":"Indian Ocean (South)"},{"lat":-34.3568,"lon":18.4740,"name":"Cape of Good Hope"},{"lat":-15.0,"lon":-5.0,"name":"South Atlantic"},{"lat":10.0,"lon":-20.0,"name":"Central Atlantic"}]',550),
('panama','Suez Canal + Asia Route','Avoids Panama Canal — eliminates lock queue delays and draft restrictions','Choose when Panama Canal has drought restrictions or lock queue > 7 days.','[{"lat":-20.0,"lon":-70.0,"name":"South Pacific"},{"lat":-55.98,"lon":-67.27,"name":"Cape Horn"},{"lat":-35.0,"lon":-50.0,"name":"South Atlantic"}]',550),
('malacca','Lombok Strait (Indonesia)','Avoids Malacca congestion — routes through Lombok Strait (deeper draft, less traffic)','Choose when Malacca has piracy alerts or extreme traffic density.','[{"lat":-8.4,"lon":115.7,"name":"Lombok Strait"},{"lat":-8.0,"lon":80.0,"name":"Indian Ocean"}]',550);

