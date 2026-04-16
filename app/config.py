"""
app/config.py — All configuration loaded from environment variables
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    # MySQL
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "shipment_risk_db")

    # External APIs
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
    AISSTREAM_API_KEY = os.getenv("AISSTREAM_API_KEY", "")
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # Cache TTLs (seconds)
    WEATHER_CACHE_TTL = int(os.getenv("WEATHER_CACHE_TTL", "3600"))    # 1 hour
    NEWS_CACHE_TTL = int(os.getenv("NEWS_CACHE_TTL", "21600"))          # 6 hours

    # Agent settings
    AGENT_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "2"))
    MAX_GRAPH_ITERATIONS = int(os.getenv("MAX_GRAPH_ITERATIONS", "5"))

    # ── Auth & Security ──────────────────────────────────────────
    # Fernet symmetric key for PII encryption (email stored encrypted in DB)
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY = os.getenv("FERNET_KEY", "")

    # JWT signing secret (access token 15 min / refresh token 7 days)
    JWT_SECRET = os.getenv("JWT_SECRET", "jwt-dev-secret-change-in-production")
    JWT_ACCESS_TTL_MINUTES = int(os.getenv("JWT_ACCESS_TTL_MINUTES", "15"))
    JWT_REFRESH_TTL_DAYS = int(os.getenv("JWT_REFRESH_TTL_DAYS", "7"))

    # SMTP for MFA OTP emails
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "AgentRouteAI <noreply@agentroute.ai>")

    # Set OTP_ENABLED=false in .env to skip MFA during development
    OTP_ENABLED = os.getenv("OTP_ENABLED", "false").lower() == "true"

    # ── Google OAuth 2.0 ─────────────────────────────────────────
    GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    # Base URL for OAuth redirect (change to your ngrok/production URL if needed)
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:5000")
