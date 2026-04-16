"""
app/agents/memory.py — Persistent Memory & Learning System

This is what gives the system institutional knowledge:
  - Stores past analyses indexed by port, route, cargo
  - Recalls similar past assessments for context
  - Tracks prediction accuracy (did the predicted risk materialize?)
  - Learns port-specific patterns over time

Agentic behaviour:
  - Before analysis: recalls similar past analyses
  - After analysis: stores result with embeddings for future recall
  - Periodically: computes prediction accuracy metrics
"""
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryAgent:
    """
    Persistent memory — makes the system learn from experience.
    Unlike stateless pipelines, this agent remembers past analyses
    and uses them to inform future assessments.
    """

    def __init__(self, db_execute, config: dict):
        self.execute = db_execute
        self.config = config

    # ─── Recall: Find similar past analyses ───────────────────
    def recall(self, port: str, cargo_type: str, session_id: str) -> dict:
        """
        Search memory for similar past analyses.
        Returns relevant past assessments and learned patterns.
        """
        logs = []
        result = {
            "similar_analyses": [],
            "prediction_accuracy": None,
            "learned_patterns": [],
            "memory_count": 0,
            "logs": logs,
        }

        if not port:
            logs.append(self._log("No port for memory search — skipping recall", "skipped"))
            return result

        logs.append(self._log(f"Searching memory for past analyses: {port}", "started"))

        # ── Query 1: Same port analyses ───────────────────────
        try:
            similar = self.execute(
                """SELECT s.session_id, s.query_text, s.port, s.cargo_type,
                          ra.risk_score, ra.risk_level, ra.delay_probability,
                          ra.factors_json, ra.llm_reasoning, s.created_at
                   FROM risk_assessments ra
                   JOIN shipments s ON ra.session_id = s.session_id
                   WHERE LOWER(s.port) LIKE LOWER(%s)
                     AND s.session_id != %s
                   ORDER BY s.created_at DESC
                   LIMIT 5""",
                (f"%{port}%", session_id), fetch=True,
            )

            if similar:
                for row in similar:
                    if row.get("created_at"):
                        row["created_at"] = row["created_at"].isoformat()
                    if row.get("factors_json") and isinstance(row["factors_json"], str):
                        try:
                            row["factors_json"] = json.loads(row["factors_json"])
                        except (json.JSONDecodeError, TypeError):
                            pass

                result["similar_analyses"] = similar
                result["memory_count"] = len(similar)

                # Calculate average past risk for this port
                scores = [r["risk_score"] for r in similar if r.get("risk_score") is not None]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    logs.append(self._log(
                        f"Found {len(similar)} past analyses for {port} — "
                        f"avg risk score: {avg_score:.0f}/100",
                        "success",
                        {"count": len(similar), "avg_score": avg_score}
                    ))

                    # Derive learned pattern
                    result["learned_patterns"].append({
                        "pattern": "historical_average",
                        "detail": f"Past {len(scores)} analyses averaged {avg_score:.0f}/100 risk score for {port}",
                        "avg_score": avg_score,
                        "min_score": min(scores),
                        "max_score": max(scores),
                    })
                else:
                    logs.append(self._log(
                        f"Found {len(similar)} records but no scored analyses",
                        "skipped"
                    ))
            else:
                logs.append(self._log(
                    f"No past analyses found for {port} — this is a first-time assessment",
                    "skipped"
                ))
        except Exception as e:
            logger.warning(f"[memory] Recall query error: {e}")
            logs.append(self._log(f"Memory recall error: {e}", "failed"))

        # ── Query 2: Same cargo type patterns ─────────────────
        if cargo_type and cargo_type != "general":
            try:
                cargo_rows = self.execute(
                    """SELECT AVG(ra.risk_score) AS avg_score,
                              COUNT(*) AS count,
                              AVG(ra.delay_probability) AS avg_delay_prob
                       FROM risk_assessments ra
                       JOIN shipments s ON ra.session_id = s.session_id
                       WHERE s.cargo_type = %s AND ra.risk_score IS NOT NULL
                       """,
                    (cargo_type,), fetch=True,
                )
                if cargo_rows and cargo_rows[0].get("count", 0) > 0:
                    row = cargo_rows[0]
                    result["learned_patterns"].append({
                        "pattern": "cargo_type_baseline",
                        "detail": f"{cargo_type} cargo averages {row['avg_score']:.0f}/100 risk "
                                  f"across {row['count']} analyses",
                        "avg_score": float(row["avg_score"]) if row["avg_score"] else 0,
                        "count": row["count"],
                    })
                    logs.append(self._log(
                        f"Cargo pattern: {cargo_type} → avg risk {row['avg_score']:.0f}/100 "
                        f"({row['count']} analyses)",
                        "success"
                    ))
            except Exception as e:
                logger.debug(f"[memory] Cargo pattern query error: {e}")

        # ── Query 3: Prediction accuracy ──────────────────────
        try:
            accuracy = self._get_prediction_accuracy(port)
            if accuracy:
                result["prediction_accuracy"] = accuracy
                logs.append(self._log(
                    f"Prediction accuracy for {port}: {accuracy.get('accuracy_pct', 'N/A')}%",
                    "success"
                ))
        except Exception as e:
            logger.debug(f"[memory] Accuracy query error: {e}")

        logs.append(self._log(
            f"Memory recall complete — {result['memory_count']} similar analyses, "
            f"{len(result['learned_patterns'])} patterns found",
            "success"
        ))

        result["logs"] = logs
        return result

    # ─── Store: Save analysis for future recall ───────────────
    def store(self, session_id: str, port: str, cargo_type: str,
              risk_score: int, risk_level: str, factors: list):
        """
        Store a completed analysis in memory for future recall.
        Called automatically after each analysis completes.
        """
        try:
            # Create a memory fingerprint for deduplication
            fingerprint = hashlib.md5(
                f"{port}:{cargo_type}:{risk_score}".encode()
            ).hexdigest()

            self.execute(
                """INSERT INTO analysis_memory
                       (session_id, port, cargo_type, risk_score, risk_level,
                        factors_summary, fingerprint, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                   ON DUPLICATE KEY UPDATE
                       risk_score=VALUES(risk_score),
                       risk_level=VALUES(risk_level),
                       factors_summary=VALUES(factors_summary)""",
                (session_id, port, cargo_type, risk_score, risk_level,
                 json.dumps(factors[:3]) if factors else "[]", fingerprint),
            )
            logger.info(f"[memory] Stored analysis: {port} → {risk_score}/100")
        except Exception as e:
            logger.warning(f"[memory] Store error: {e}")

    # ─── Record prediction outcome ────────────────────────────
    def record_outcome(self, session_id: str, actual_delay_days: int,
                       actual_issues: str = None):
        """
        Record the actual outcome of a prediction.
        Called via POST /api/feedback when user reports what actually happened.
        """
        try:
            self.execute(
                """INSERT INTO prediction_outcomes
                       (session_id, actual_delay_days, actual_issues, reported_at)
                   VALUES (%s, %s, %s, NOW())
                   ON DUPLICATE KEY UPDATE
                       actual_delay_days=VALUES(actual_delay_days),
                       actual_issues=VALUES(actual_issues)""",
                (session_id, actual_delay_days, actual_issues),
            )
            logger.info(f"[memory] Outcome recorded for session {session_id}")
        except Exception as e:
            logger.warning(f"[memory] Outcome recording error: {e}")

    # ─── Prediction accuracy calculation ──────────────────────
    def _get_prediction_accuracy(self, port: str) -> Optional[dict]:
        """
        Calculate how accurate past predictions were for this port.
        Compares predicted risk/delay with actual outcomes.
        """
        try:
            rows = self.execute(
                """SELECT
                    ra.risk_score AS predicted_score,
                    ra.delay_probability AS predicted_delay_pct,
                    po.actual_delay_days,
                    s.port
                FROM prediction_outcomes po
                JOIN risk_assessments ra ON po.session_id = ra.session_id
                JOIN shipments s ON po.session_id = s.session_id
                WHERE LOWER(s.port) LIKE LOWER(%s)
                LIMIT 20""",
                (f"%{port}%",), fetch=True,
            )

            if not rows:
                return None

            # Simple accuracy: did we predict delay when delay occurred?
            correct = 0
            total = len(rows)
            for row in rows:
                predicted_high = (row.get("predicted_score", 0) or 0) > 50
                actual_delayed = (row.get("actual_delay_days", 0) or 0) > 0
                if predicted_high == actual_delayed:
                    correct += 1

            accuracy_pct = round((correct / total) * 100, 1) if total > 0 else None

            return {
                "accuracy_pct": accuracy_pct,
                "total_predictions": total,
                "correct_predictions": correct,
            }
        except Exception as e:
            logger.debug(f"[memory] Accuracy calculation error: {e}")
            return None

    # ─── Analytics ────────────────────────────────────────────
    def get_analytics(self) -> dict:
        """
        Return system-wide analytics for the dashboard.
        """
        try:
            # Total analyses
            totals = self.execute(
                "SELECT COUNT(*) AS total, AVG(risk_score) AS avg_score "
                "FROM risk_assessments WHERE risk_score IS NOT NULL",
                fetch=True,
            )

            # By port
            by_port = self.execute(
                """SELECT s.port, COUNT(*) AS count, AVG(ra.risk_score) AS avg_score
                FROM risk_assessments ra
                JOIN shipments s ON ra.session_id = s.session_id
                WHERE ra.risk_score IS NOT NULL AND s.port IS NOT NULL
                GROUP BY s.port
                ORDER BY count DESC
                LIMIT 10""",
                fetch=True,
            )

            # By risk level
            by_level = self.execute(
                """SELECT risk_level, COUNT(*) AS count
                FROM risk_assessments WHERE risk_level IS NOT NULL
                GROUP BY risk_level""",
                fetch=True,
            )

            # Recent trend
            recent = self.execute(
                """SELECT DATE(s.created_at) AS date, COUNT(*) AS count,
                          AVG(ra.risk_score) AS avg_score
                FROM risk_assessments ra
                JOIN shipments s ON ra.session_id = s.session_id
                WHERE s.created_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
                GROUP BY DATE(s.created_at)
                ORDER BY date""",
                fetch=True,
            )

            # Serialize dates
            for row in recent or []:
                if row.get("date"):
                    row["date"] = row["date"].isoformat()

            return {
                "total_analyses": totals[0]["total"] if totals else 0,
                "avg_risk_score": float(totals[0]["avg_score"]) if totals and totals[0]["avg_score"] else 0,
                "by_port": by_port or [],
                "by_risk_level": by_level or [],
                "recent_trend": recent or [],
            }
        except Exception as e:
            logger.warning(f"[memory] Analytics error: {e}")
            return {"total_analyses": 0, "avg_risk_score": 0, "by_port": [],
                    "by_risk_level": [], "recent_trend": []}

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "memory", "action": action, "status": status, "data": data}
