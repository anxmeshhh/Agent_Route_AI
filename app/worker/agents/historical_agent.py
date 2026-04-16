"""
app/agents/historical_agent.py — Module 4

Queries the seeded MySQL historical_shipments table to find
seasonal delay patterns for the target port.
Zero LLM calls — pure SQL analytics and rule-based scoring.

Agentic behaviour:
  - Queries DB for same port, same month (past 2 years)
  - Calculates delay rate, average delay days, peak seasons
  - Returns partial risk score (0–30) with explanation
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class HistoricalAgent:
    """
    Module 4: Historical delay pattern analysis from seeded MySQL records.
    """

    def __init__(self, db_execute, config: dict):
        self.execute = db_execute

    def run(self, port: str, eta_days: int, cargo_type: str, session_id: str) -> dict:
        """
        Returns historical risk dict:
        {
            "port": str,
            "records_analysed": int,
            "delay_rate": float,        # 0.0–1.0
            "avg_delay_days": float,
            "seasonal_risk": str,       # LOW/MEDIUM/HIGH
            "risk_signals": [...],
            "historical_score": int,    # 0–30
            "logs": [...]
        }
        """
        logs = []
        result = {
            "port": port,
            "records_analysed": 0,
            "delay_rate": 0.0,
            "avg_delay_days": 0.0,
            "seasonal_risk": "LOW",
            "risk_signals": [],
            "historical_score": 0,
            "logs": logs,
        }

        if not port:
            logs.append(self._log("No port specified — skipping historical analysis", "skipped"))
            result["historical_score"] = 5  # small default
            return result

        current_month = datetime.utcnow().month

        # ── Query 1: Overall delay rate for this port ──────────────
        logs.append(self._log(f"Querying historical delay records for port: {port}", "started"))
        try:
            overall = self._query_overall(port)
            total_records = overall.get("total", 0)
            delayed_count = overall.get("delayed", 0)
            avg_days      = overall.get("avg_delay", 0) or 0

            result["records_analysed"] = total_records

            if total_records > 0:
                delay_rate = delayed_count / total_records
                result["delay_rate"]     = round(delay_rate, 3)
                result["avg_delay_days"] = round(float(avg_days), 1)
                logs.append(self._log(
                    f"Found {total_records} records — delay rate: {delay_rate*100:.1f}%, "
                    f"avg delay: {avg_days:.1f} days",
                    "success",
                    {"total": total_records, "delay_rate": delay_rate},
                ))
            else:
                logs.append(self._log(
                    f"No direct history for {port} — using global baseline",
                    "skipped",
                ))
                result["delay_rate"] = 0.18  # global average
                result["avg_delay_days"] = 2.1
                result["records_analysed"] = 0

        except Exception as e:
            logger.warning(f"[historical] DB query error: {e}")
            logs.append(self._log(f"DB query failed: {e}", "failed"))
            result["delay_rate"] = 0.18

        # ── Query 2: Seasonal pattern for this month ───────────────
        logs.append(self._log(
            f"Checking seasonal risk for month {current_month} at {port}", "started"
        ))
        try:
            seasonal = self._query_seasonal(port, current_month)
            seasonal_rate = seasonal.get("rate", 0) or 0
            result["seasonal_risk"] = self._classify_seasonal(float(seasonal_rate))
            logs.append(self._log(
                f"Seasonal delay rate this month: {seasonal_rate*100:.1f}% → {result['seasonal_risk']} risk",
                "success",
                {"month": current_month, "seasonal_rate": seasonal_rate},
            ))
        except Exception as e:
            logger.warning(f"[historical] Seasonal query error: {e}")
            logs.append(self._log("Seasonal query failed — using estimate", "failed"))
            result["seasonal_risk"] = "MEDIUM"

        # ── Query 3: Cargo-type specific delays ────────────────────
        cargo_context = ""
        if cargo_type and cargo_type != "general":
            try:
                cargo_data = self._query_cargo(port, cargo_type)
                if cargo_data.get("total", 0) > 0:
                    cargo_rate = (cargo_data.get("delayed", 0) / cargo_data["total"])
                    cargo_context = f"{cargo_type} cargo has {cargo_rate*100:.0f}% delay rate at this port"
                    logs.append(self._log(
                        f"Cargo-specific ({cargo_type}): {cargo_rate*100:.0f}% delay rate",
                        "success",
                    ))
            except Exception:
                pass

        # ── Build risk signals ─────────────────────────────────────
        signals = []
        score   = 0

        delay_rate = result["delay_rate"]
        avg_delay  = result["avg_delay_days"]

        if delay_rate >= 0.50:
            signals.append({
                "type": "historical", "severity": "HIGH",
                "title": f"High historical delay rate: {delay_rate*100:.0f}%",
                "detail": f"Over half of shipments to {port} experience delays. Avg: {avg_delay:.1f} days.",
            })
            score += 22
        elif delay_rate >= 0.30:
            signals.append({
                "type": "historical", "severity": "MEDIUM",
                "title": f"Moderate delay history: {delay_rate*100:.0f}%",
                "detail": f"Significant proportion of shipments delayed. Avg: {avg_delay:.1f} days.",
            })
            score += 14
        elif delay_rate >= 0.15:
            signals.append({
                "type": "historical", "severity": "LOW",
                "title": f"Low-moderate delay rate: {delay_rate*100:.0f}%",
                "detail": f"Some historical delays at {port}. Avg: {avg_delay:.1f} days.",
            })
            score += 7

        if result["seasonal_risk"] == "HIGH":
            signals.append({
                "type": "historical", "severity": "HIGH",
                "title": "Peak season congestion period",
                "detail": f"Historical data shows elevated delays in the current month at {port}.",
            })
            score += 8
        elif result["seasonal_risk"] == "MEDIUM":
            signals.append({
                "type": "historical", "severity": "MEDIUM",
                "title": "Moderate seasonal congestion expected",
                "detail": f"Current month has moderate historical delay rate at {port}.",
            })
            score += 4

        if eta_days and eta_days <= 2 and delay_rate > 0.2:
            signals.append({
                "type": "historical", "severity": "MEDIUM",
                "title": "Short lead time with elevated delay history",
                "detail": f"Only {eta_days} day(s) to arrival — recovery time is limited.",
            })
            score += 4

        if cargo_context:
            signals.append({
                "type": "historical", "severity": "LOW",
                "title": f"Cargo-specific pattern: {cargo_type}",
                "detail": cargo_context,
            })

        result["risk_signals"]      = signals
        result["historical_score"]  = min(score, 30)

        logs.append(self._log(
            f"Historical risk scored: {result['historical_score']}/30 "
            f"— {len(signals)} pattern(s) identified",
            "success",
            {"score": result["historical_score"]},
        ))

        result["logs"] = logs
        return result

    # ─── DB Queries ───────────────────────────────────────────────
    def _query_overall(self, port: str) -> dict:
        rows = self.execute(
            """SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) AS delayed_count,
                AVG(CASE WHEN delay_days > 0 THEN delay_days ELSE NULL END) AS avg_delay
               FROM historical_shipments
               WHERE LOWER(port) LIKE LOWER(%s)""",
            (f"%{port}%",), fetch=True,
        )
        row = rows[0] if rows else {}
        # normalise the alias back to what callers expect
        if row and "delayed_count" in row:
            row["delayed"] = row.pop("delayed_count")
        return row

    def _query_seasonal(self, port: str, month: int) -> dict:
        rows = self.execute(
            """SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) / COUNT(*) AS rate
               FROM historical_shipments
               WHERE LOWER(port) LIKE LOWER(%s) AND month = %s""",
            (f"%{port}%", month), fetch=True,
        )
        if rows and rows[0].get("total", 0):
            return rows[0]
        # Global seasonal estimate if port not in DB
        high_months  = [11, 12, 1, 7, 8]  # peak shipping, summer
        med_months   = [2, 3, 6, 9, 10]
        if month in high_months:
            return {"rate": 0.42}
        elif month in med_months:
            return {"rate": 0.28}
        return {"rate": 0.18}

    def _query_cargo(self, port: str, cargo_type: str) -> dict:
        rows = self.execute(
            """SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN delay_days > 0 THEN 1 ELSE 0 END) AS delayed
               FROM historical_shipments
               WHERE LOWER(port) LIKE LOWER(%s) AND cargo_type = %s""",
            (f"%{port}%", cargo_type), fetch=True,
        )
        return rows[0] if rows else {}

    def _classify_seasonal(self, rate: float) -> str:
        if rate >= 0.40: return "HIGH"
        if rate >= 0.25: return "MEDIUM"
        return "LOW"

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "historical", "action": action, "status": status, "data": data}
