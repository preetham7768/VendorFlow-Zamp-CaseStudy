"""
SQLite Database Layer for VendorFlow.
Handles persistence for:
- Execution runs (with redacted inputs, stage results, and decisions)
- Approved vendors registry (with hashed tax IDs)
- Restricted vendors registry (synthetic demo data)
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "vendorflow.db"


def hash_identifier(value: Optional[str]) -> str:
    """Computes a SHA-256 hash of a normalized identifier."""
    if not value:
        return ""
    normalized = value.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Creates a connection with row factory configured."""
    target_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes the database schema and populates synthetic seed data if empty."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()

            # Table 1: runs
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    vendor_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    processing_duration_ms REAL NOT NULL,
                    run_type TEXT NOT NULL,
                    issues_count INTEGER DEFAULT 0,
                    redacted_input_json TEXT NOT NULL,
                    stage_results_json TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    communication_draft TEXT NOT NULL
                )
                """
            )

            # Table 2: approved_vendors
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS approved_vendors (
                    vendor_id TEXT PRIMARY KEY,
                    vendor_name TEXT NOT NULL,
                    pan_hash TEXT NOT NULL,
                    gstin_hash TEXT NOT NULL,
                    approved_at TEXT NOT NULL,
                    source_run_id TEXT
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_approved_pan ON approved_vendors(pan_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_approved_gstin ON approved_vendors(gstin_hash)"
            )

            # Table 3: restricted_vendors
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS restricted_vendors (
                    restricted_id TEXT PRIMARY KEY,
                    vendor_name TEXT NOT NULL,
                    pan_hash TEXT NOT NULL,
                    gstin_hash TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    added_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_restricted_pan ON restricted_vendors(pan_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_restricted_gstin ON restricted_vendors(gstin_hash)"
            )

            # Seed synthetic records for predictable demonstration scenarios
            # Scenario D seed: Existing approved vendor (Northstar Office Supplies)
            pan_seed = "LMNOP1234Q"
            gstin_seed = "27LMNOP1234Q1Z5"
            pan_hash_seed = hash_identifier(pan_seed)
            gstin_hash_seed = hash_identifier(gstin_seed)

            cursor.execute(
                "SELECT COUNT(*) as cnt FROM approved_vendors WHERE pan_hash = ?",
                (pan_hash_seed,),
            )
            if cursor.fetchone()["cnt"] == 0:
                cursor.execute(
                    """
                    INSERT INTO approved_vendors (vendor_id, vendor_name, pan_hash, gstin_hash, approved_at, source_run_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "SEED-APP-001",
                        "Northstar Office Supplies Private Limited",
                        pan_hash_seed,
                        gstin_hash_seed,
                        datetime.now(timezone.utc).isoformat(),
                        "SYSTEM_SEED",
                    ),
                )

            # Scenario E seed: Synthetic restricted vendor (Redwood Logistics LLP)
            pan_restr = "UVWXY5678Z"
            gstin_restr = "29UVWXY5678Z1Z5"
            pan_hash_restr = hash_identifier(pan_restr)
            gstin_hash_restr = hash_identifier(gstin_restr)

            cursor.execute(
                "SELECT COUNT(*) as cnt FROM restricted_vendors WHERE pan_hash = ?",
                (pan_hash_restr,),
            )
            if cursor.fetchone()["cnt"] == 0:
                cursor.execute(
                    """
                    INSERT INTO restricted_vendors (restricted_id, vendor_name, pan_hash, gstin_hash, reason, added_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "SEED-RESTR-001",
                        "Redwood Logistics LLP",
                        pan_hash_restr,
                        gstin_hash_restr,
                        "Internal compliance policy flag - high risk entity (Synthetic Watchlist Entry)",
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
    finally:
        conn.close()


def save_run(run_data: Dict[str, Any], db_path: Optional[Path] = None) -> None:
    """Inserts a new execution run record."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO runs (
                    run_id, created_at, vendor_name, status, processing_duration_ms,
                    run_type, issues_count, redacted_input_json, stage_results_json,
                    decision_json, communication_draft
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_data["run_id"],
                    run_data["created_at"],
                    run_data["vendor_name"],
                    run_data["status"],
                    run_data["processing_duration_ms"],
                    run_data.get("run_type", "Live Submission"),
                    run_data.get("issues_count", 0),
                    json.dumps(run_data.get("redacted_input", {})),
                    json.dumps(run_data.get("stage_results", [])),
                    json.dumps(run_data.get("decision", {})),
                    run_data.get("communication_draft", ""),
                ),
            )
    finally:
        conn.close()


def add_approved_vendor(
    vendor_id: str,
    vendor_name: str,
    pan_hash: str,
    gstin_hash: str,
    source_run_id: str,
    db_path: Optional[Path] = None,
) -> None:
    """Adds a newly approved vendor to the approved vendors registry."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO approved_vendors (vendor_id, vendor_name, pan_hash, gstin_hash, approved_at, source_run_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    vendor_id,
                    vendor_name,
                    pan_hash,
                    gstin_hash,
                    datetime.now(timezone.utc).isoformat(),
                    source_run_id,
                ),
            )
    finally:
        conn.close()


def check_duplicate(
    pan_hash: str, gstin_hash: str, db_path: Optional[Path] = None
) -> Tuple[bool, Optional[str]]:
    """
    Checks if a vendor with matching PAN or GSTIN hash already exists in approved_vendors.
    Returns (is_duplicate, matched_vendor_name).
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT vendor_name FROM approved_vendors
            WHERE (pan_hash = ? AND pan_hash != '')
               OR (gstin_hash = ? AND gstin_hash != '')
            LIMIT 1
            """,
            (pan_hash, gstin_hash),
        )
        row = cursor.fetchone()
        if row:
            return True, row["vendor_name"]
        return False, None
    finally:
        conn.close()


def check_restricted(
    pan_hash: str, gstin_hash: str, db_path: Optional[Path] = None
) -> Tuple[bool, Optional[str]]:
    """
    Checks if a vendor with matching PAN or GSTIN hash is in the restricted registry.
    Returns (is_restricted, reason).
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT reason, vendor_name FROM restricted_vendors
            WHERE (pan_hash = ? AND pan_hash != '')
               OR (gstin_hash = ? AND gstin_hash != '')
            LIMIT 1
            """,
            (pan_hash, gstin_hash),
        )
        row = cursor.fetchone()
        if row:
            return True, row["reason"]
        return False, None
    finally:
        conn.close()


def get_all_runs(
    db_path: Optional[Path] = None,
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieves runs from SQLite with optional filtering."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        query = "SELECT * FROM runs WHERE 1=1"
        params: List[Any] = []

        if status_filter and status_filter != "ALL":
            query += " AND status = ?"
            params.append(status_filter)

        if search_query:
            query += " AND (vendor_name LIKE ? OR run_id LIKE ?)"
            like_val = f"%{search_query.strip()}%"
            params.extend([like_val, like_val])

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        runs = []
        for r in rows:
            runs.append(
                {
                    "run_id": r["run_id"],
                    "created_at": r["created_at"],
                    "vendor_name": r["vendor_name"],
                    "status": r["status"],
                    "processing_duration_ms": r["processing_duration_ms"],
                    "run_type": r["run_type"],
                    "issues_count": r["issues_count"],
                    "redacted_input": json.loads(r["redacted_input_json"]),
                    "stage_results": json.loads(r["stage_results_json"]),
                    "decision": json.loads(r["decision_json"]),
                    "communication_draft": r["communication_draft"],
                }
            )
        return runs
    finally:
        conn.close()


def get_run_by_id(run_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Retrieves a single run by run_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        r = cursor.fetchone()
        if not r:
            return None
        return {
            "run_id": r["run_id"],
            "created_at": r["created_at"],
            "vendor_name": r["vendor_name"],
            "status": r["status"],
            "processing_duration_ms": r["processing_duration_ms"],
            "run_type": r["run_type"],
            "issues_count": r["issues_count"],
            "redacted_input": json.loads(r["redacted_input_json"]),
            "stage_results": json.loads(r["stage_results_json"]),
            "decision": json.loads(r["decision_json"]),
            "communication_draft": r["communication_draft"],
        }
    finally:
        conn.close()


def get_dashboard_metrics(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Calculates summary counts and rates for the execution dashboard."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM runs")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as approved FROM runs WHERE status = 'APPROVED'")
        approved = cursor.fetchone()["approved"]

        cursor.execute("SELECT COUNT(*) as pending FROM runs WHERE status = 'PENDING'")
        pending = cursor.fetchone()["pending"]

        cursor.execute("SELECT COUNT(*) as rejected FROM runs WHERE status = 'REJECTED'")
        rejected = cursor.fetchone()["rejected"]

        approval_rate = (approved / total * 100.0) if total > 0 else 0.0

        return {
            "total_submissions": total,
            "approved": approved,
            "pending": pending,
            "rejected": rejected,
            "approval_rate": round(approval_rate, 1),
        }
    finally:
        conn.close()
