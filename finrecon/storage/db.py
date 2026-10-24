import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from finrecon.models import (
    ReconciliationSummary, ReconciliationMatch, Anomaly,
    Transaction, AuditLogEntry
)
from finrecon.config import ReconciliationConfig, DEFAULT_CONFIG

class StorageManager:
    """SQLite and in-memory persistence manager for runs, audit logs, and manual overrides."""

    def __init__(self, config: Optional[ReconciliationConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.db_path = self.config.sqlite_db_path
        self._ensure_storage()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
        self._active_run: Optional[Dict[str, Any]] = None

    def _ensure_storage(self):
        try:
            self.config.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        try:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        except Exception:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_runs (
                    run_id TEXT PRIMARY KEY,
                    executed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    summary_json TEXT NOT NULL
                )
            """)
            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    log_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details_json TEXT NOT NULL
                )
            """)
            # Manual resolutions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS manual_resolutions (
                    resolution_id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_run(self, run_data: Dict[str, Any]):
        """Cache run data in-memory and record run to SQLite."""
        self._active_run = run_data
        summary: ReconciliationSummary = run_data["summary"]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO reconciliation_runs 
                (run_id, executed_at, status, duration_ms, summary_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    summary.run_id,
                    summary.executed_at.isoformat(),
                    summary.status,
                    summary.duration_ms,
                    summary.model_dump_json() if hasattr(summary, "model_dump_json") else json.dumps(summary.dict())
                )
            )
            # Log automated run creation
            cursor.execute(
                """
                INSERT INTO audit_logs (log_id, run_id, timestamp, action, entity_id, actor, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"LOG-{uuid.uuid4().hex[:8]}",
                    summary.run_id,
                    datetime.utcnow().isoformat(),
                    "RUN_COMPLETED",
                    summary.run_id,
                    "FINRECON_AUTOMATION_ENGINE",
                    json.dumps({
                        "matched_records": summary.matched_records_count,
                        "match_rate": summary.match_rate_pct,
                        "anomalies": summary.anomaly_count
                    })
                )
            )
            conn.commit()

    def get_active_run(self) -> Optional[Dict[str, Any]]:
        return self._active_run

    def record_manual_resolution(
        self,
        target_id: str,
        target_type: str,
        action: str,
        operator_id: str,
        notes: str
    ) -> Dict[str, Any]:
        """Record manual controller decision and audit log entry."""
        res_id = f"RES-{uuid.uuid4().hex[:8]}"
        log_id = f"LOG-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow().isoformat()
        current_run_id = self._active_run["run_id"] if self._active_run else "GLOBAL"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO manual_resolutions (resolution_id, target_id, target_type, action, operator_id, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (res_id, target_id, target_type, action, operator_id, notes, now)
            )
            cursor.execute(
                """
                INSERT INTO audit_logs (log_id, run_id, timestamp, action, entity_id, actor, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    current_run_id,
                    now,
                    f"MANUAL_{action}",
                    target_id,
                    operator_id,
                    json.dumps({"target_type": target_type, "notes": notes})
                )
            )
            conn.commit()

        # Update in-memory active run if present
        if self._active_run:
            for anom in self._active_run.get("anomalies", []):
                if anom.anomaly_id == target_id:
                    anom.status = action
                    break

        return {
            "resolution_id": res_id,
            "log_id": log_id,
            "target_id": target_id,
            "status": action,
            "timestamp": now
        }

    def get_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT log_id, run_id, timestamp, action, entity_id, actor, details_json FROM audit_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            logs = []
            for r in rows:
                logs.append({
                    "log_id": r["log_id"],
                    "run_id": r["run_id"],
                    "timestamp": r["timestamp"],
                    "action": r["action"],
                    "entity_id": r["entity_id"],
                    "actor": r["actor"],
                    "details": json.loads(r["details_json"])
                })
            return logs
