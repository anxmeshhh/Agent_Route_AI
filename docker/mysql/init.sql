-- ============================================================
-- AgentRouteAI — MySQL Initialization Script
-- Runs automatically on first container start
-- ============================================================

-- Create the database if not exists
CREATE DATABASE IF NOT EXISTS shipment_risk_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE shipment_risk_db;

-- Create the application user with limited privileges
CREATE USER IF NOT EXISTS 'agentroute'@'%' IDENTIFIED BY 'AgentRoute@2026!';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER
    ON shipment_risk_db.* TO 'agentroute'@'%';
FLUSH PRIVILEGES;
