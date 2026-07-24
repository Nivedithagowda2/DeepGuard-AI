"""
database.py
-----------
Covers Step 7 of the build plan: Logging verification attempts.

Role in the architecture: "The Record Keeper" — plays the role your real Cloud
AI 100 would eventually play: storing a history of every verification attempt,
without storing anyone's actual face image (only the outcome).

Uses SQLite - a single file on disk, no separate server needed. Perfect for a
hackathon demo's scale.

Now also tracks processing_time_ms - average per-frame processing latency
during the verification recording window. This directly supports the "latency
and performance" criterion in the hackathon's Technical Implementation scoring
(40 of 100 points) by giving you a real, visible number to show judges, instead
of just claiming the system is fast.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "deepguard.db")


def init_db():
    """Creates the verifications table if it doesn't already exist, and
    migrates older database files (from before latency tracking was added)
    by adding the new column if it's missing. Safe to call every time the
    app starts."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            risk_score INTEGER NOT NULL,
            blink_detected INTEGER NOT NULL,
            spoof_score REAL NOT NULL,
            reasons TEXT,
            processing_time_ms REAL
        )
    """)

    # Migration for databases created before processing_time_ms existed
    cursor.execute("PRAGMA table_info(verifications)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    if "processing_time_ms" not in existing_columns:
        cursor.execute("ALTER TABLE verifications ADD COLUMN processing_time_ms REAL")

    conn.commit()
    conn.close()


def log_verification(status, risk_score, blink_detected, spoof_score, reasons,
                      processing_time_ms=None):
    """Inserts one verification attempt record. Called by dashboard.py
    every time a verification attempt is finalized."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO verifications
            (timestamp, status, risk_score, blink_detected, spoof_score, reasons, processing_time_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        status,
        risk_score,
        1 if blink_detected else 0,
        spoof_score,
        ", ".join(reasons) if isinstance(reasons, list) else str(reasons),
        processing_time_ms,
    ))
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_history(limit=50):
    """Returns the most recent verification attempts, newest first.
    Used by the Supervisor Dashboard page (Step 8)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, status, risk_score, blink_detected, spoof_score,
               reasons, processing_time_ms
        FROM verifications
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    # Standalone test - run `python database.py` to verify the DB works,
    # without needing the webcam, AI model, or FastAPI running.
    print(f"Initializing database at: {DB_PATH}")
    init_db()

    print("Inserting sample records...")
    log_verification("VERIFIED", 3, True, 0.96, ["All liveness checks passed"],
                      processing_time_ms=42.5)
    log_verification("HIGH RISK", 97, False, 0.12,
                      ["Low real-face confidence (0.12)", "No natural blink detected"],
                      processing_time_ms=38.1)

    print("\nHistory (most recent first):")
    for record in get_history():
        print(f"  #{record['id']} | {record['timestamp']} | {record['status']} "
              f"| risk={record['risk_score']} | spoof={record['spoof_score']} "
              f"| latency={record['processing_time_ms']}ms")
