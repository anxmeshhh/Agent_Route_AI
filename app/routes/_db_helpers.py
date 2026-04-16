"""
app/routes/_db_helpers.py — Database helper functions for the API pipeline.

Three small wrappers used exclusively by the /analyze pipeline:
  _store_shipment    — INSERT into shipments, returns last insert ID
  _update_shipment_status — UPDATE shipments.status
  _log_to_db         — INSERT into agent_logs
"""
import json
import logging

from ..database import execute_query

logger = logging.getLogger(__name__)


def _store_shipment(session_id: str, intake_result: dict, org_id: int = 1) -> int:
    """Insert a new shipment row. org_id tags it to the user's organisation."""
    return execute_query(
        """
        INSERT INTO shipments
            (session_id, query_text, port, port_city, eta_days, cargo_type,
             vessel_name, origin_port, status, org_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'running', %s)
        """,
        (
            session_id,
            intake_result["query_text"],
            intake_result.get("port"),
            intake_result.get("port_city"),
            intake_result.get("eta_days"),
            intake_result.get("cargo_type"),
            intake_result.get("vessel_name"),
            intake_result.get("origin_port"),
            org_id,
        ),
    )


def _update_shipment_status(session_id: str, status: str):
    execute_query(
        "UPDATE shipments SET status = %s WHERE session_id = %s",
        (status, session_id),
    )


def _log_to_db(session_id: str, agent: str, action: str, status: str,
               data: dict = None, duration_ms: int = None):
    execute_query(
        """
        INSERT INTO agent_logs
            (session_id, agent_name, action, status, data_json, duration_ms)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            session_id, agent, action, status,
            json.dumps(data) if data else None,
            duration_ms,
        ),
    )
