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
