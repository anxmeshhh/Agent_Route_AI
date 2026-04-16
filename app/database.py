"""
app/database.py — MySQL connection pool management
"""
import mysql.connector
from mysql.connector import pooling
from flask import current_app, g
import os


_pool = None


def init_db_pool(app):
    """Initialize the MySQL connection pool on app startup."""
    global _pool
    config = {
        "pool_name": "shipment_risk_pool",
        "pool_size": 5,
        "pool_reset_session": True,
        "host": app.config["MYSQL_HOST"],
        "port": app.config["MYSQL_PORT"],
        "user": app.config["MYSQL_USER"],
        "password": app.config["MYSQL_PASSWORD"],
        "database": app.config["MYSQL_DATABASE"],
        "charset": "utf8mb4",
        "use_unicode": True,
        "autocommit": False,
    }
    try:
        _pool = pooling.MySQLConnectionPool(**config)
        app.logger.info("✅ MySQL connection pool created")
    except mysql.connector.Error as e:
        app.logger.error(f"❌ MySQL pool creation failed: {e}")
        _pool = None


def get_db():
    """Get a MySQL connection from the pool (or Flask g cache)."""
    if "db" not in g:
        if _pool is None:
            raise RuntimeError("Database pool not initialised. Check MySQL config.")
        g.db = _pool.get_connection()
    return g.db


def close_db(e=None):
    """Return connection to pool at end of request."""
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def execute_query(query, params=None, fetch=False, many=False):
    """
    Utility: run a query on a short-lived connection.
    Returns fetched rows (list of dicts) or lastrowid.
    """
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        if many:
            cursor.executemany(query, params or [])
        else:
            cursor.execute(query, params or ())
        if fetch:
            return cursor.fetchall()
        conn.commit()
        return cursor.lastrowid
    except mysql.connector.Error as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()


def init_schema(app):
    """Create all tables from schema.sql if they don't exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "models", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # Strip single-line SQL comments (-- ...) before splitting
    import re
    cleaned = re.sub(r'--[^\n]*', '', raw)

    # Split on semicolons; skip blank / whitespace-only fragments
    statements = [s.strip() for s in cleaned.split(";")]
    statements = [s for s in statements if s and not s.isspace()]

    # Errors that are always safe to ignore
    SAFE_ERRNOS = {
        1007,  # database already exists
        1050,  # table already exists
        1060,  # duplicate column
        1061,  # duplicate key name
        1826,  # duplicate foreign key constraint
        1022,  # duplicate key (alt form)
    }

    conn = None
    try:
        conn = mysql.connector.connect(
            host=app.config["MYSQL_HOST"],
            port=app.config["MYSQL_PORT"],
            user=app.config["MYSQL_USER"],
            password=app.config["MYSQL_PASSWORD"],
            charset="utf8mb4",
        )
        cursor = conn.cursor()
        for stmt in statements:
            if stmt:
                try:
                    cursor.execute(stmt)
                except mysql.connector.Error as e:
                    if e.errno not in SAFE_ERRNOS:
                        app.logger.warning(f"Schema stmt warning: {e}")
        conn.commit()
        cursor.close()
        app.logger.info("✅ Database schema initialised")
    except mysql.connector.Error as e:
        app.logger.error(f"❌ Schema init failed: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()
