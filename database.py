"""SQLite database layer for email tracking."""

import sqlite3
import uuid
from datetime import datetime, timezone
from config import Config


def get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS recipients (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL UNIQUE,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS emails (
            id              TEXT PRIMARY KEY,
            recipient_id    TEXT NOT NULL,
            subject         TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'pending',
            sent_at         TEXT,
            error_message   TEXT,
            FOREIGN KEY (recipient_id) REFERENCES recipients(id)
        );

        CREATE TABLE IF NOT EXISTS tracking_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id    TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            metadata    TEXT,
            ip_address  TEXT,
            user_agent  TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (email_id) REFERENCES emails(id)
        );

        CREATE INDEX IF NOT EXISTS idx_emails_recipient
            ON emails(recipient_id);
        CREATE INDEX IF NOT EXISTS idx_events_email
            ON tracking_events(email_id);
        CREATE INDEX IF NOT EXISTS idx_events_type
            ON tracking_events(event_type);
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Recipients
# ---------------------------------------------------------------------------

def upsert_recipient(name: str, email: str) -> str:
    """Insert or update a recipient. Returns the recipient ID."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM recipients WHERE email = ?", (email,))
    row = cursor.fetchone()

    if row:
        rid = row["id"]
        cursor.execute(
            "UPDATE recipients SET name = ? WHERE id = ?", (name, rid)
        )
    else:
        rid = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO recipients (id, name, email) VALUES (?, ?, ?)",
            (rid, name, email),
        )

    conn.commit()
    conn.close()
    return rid


def get_all_recipients():
    """Return all recipients."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM recipients ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Emails
# ---------------------------------------------------------------------------

def create_email_record(recipient_id: str, subject: str) -> str:
    """Create a pending email record. Returns the email tracking ID."""
    eid = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        "INSERT INTO emails (id, recipient_id, subject) VALUES (?, ?, ?)",
        (eid, recipient_id, subject),
    )
    conn.commit()
    conn.close()
    return eid


def mark_email_sent(email_id: str):
    """Mark an email as successfully sent."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    conn.execute(
        "UPDATE emails SET status = 'sent', sent_at = ? WHERE id = ?",
        (now, email_id),
    )
    conn.commit()
    conn.close()


def mark_email_failed(email_id: str, error: str):
    """Mark an email as failed."""
    conn = get_connection()
    conn.execute(
        "UPDATE emails SET status = 'failed', error_message = ? WHERE id = ?",
        (error, email_id),
    )
    conn.commit()
    conn.close()


def get_all_emails():
    """Return all emails joined with recipient info."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT e.id, e.subject, e.status, e.sent_at, e.error_message,
               r.name AS recipient_name, r.email AS recipient_email
        FROM emails e
        JOIN recipients r ON e.recipient_id = r.id
        ORDER BY e.sent_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tracking events
# ---------------------------------------------------------------------------

def record_event(email_id: str, event_type: str,
                 metadata: str = None, ip: str = None, ua: str = None):
    """Record a tracking event (open, click, etc.)."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO tracking_events
           (email_id, event_type, metadata, ip_address, user_agent)
           VALUES (?, ?, ?, ?, ?)""",
        (email_id, event_type, metadata, ip, ua),
    )
    conn.commit()
    conn.close()


def get_events_for_email(email_id: str):
    """Return all events for a specific email."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM tracking_events WHERE email_id = ? ORDER BY created_at",
        (email_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_tracking_summary():
    """Return aggregate tracking stats for the dashboard."""
    conn = get_connection()

    total_sent = conn.execute(
        "SELECT COUNT(*) as c FROM emails WHERE status = 'sent'"
    ).fetchone()["c"]

    total_failed = conn.execute(
        "SELECT COUNT(*) as c FROM emails WHERE status = 'failed'"
    ).fetchone()["c"]

    total_opens = conn.execute(
        "SELECT COUNT(DISTINCT email_id) as c FROM tracking_events WHERE event_type = 'open'"
    ).fetchone()["c"]

    total_clicks = conn.execute(
        "SELECT COUNT(DISTINCT email_id) as c FROM tracking_events WHERE event_type = 'click'"
    ).fetchone()["c"]

    # Per-email detail
    rows = conn.execute("""
        SELECT
            e.id,
            r.name,
            r.email,
            e.subject,
            e.status,
            e.sent_at,
            (SELECT COUNT(*) FROM tracking_events te
             WHERE te.email_id = e.id AND te.event_type = 'open') AS open_count,
            (SELECT MIN(te.created_at) FROM tracking_events te
             WHERE te.email_id = e.id AND te.event_type = 'open') AS first_opened,
            (SELECT COUNT(*) FROM tracking_events te
             WHERE te.email_id = e.id AND te.event_type = 'click') AS click_count,
            (SELECT MIN(te.created_at) FROM tracking_events te
             WHERE te.email_id = e.id AND te.event_type = 'click') AS first_clicked
        FROM emails e
        JOIN recipients r ON e.recipient_id = r.id
        ORDER BY e.sent_at DESC
    """).fetchall()

    conn.close()

    return {
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "open_rate": round(total_opens / total_sent * 100, 1) if total_sent else 0,
        "click_rate": round(total_clicks / total_sent * 100, 1) if total_sent else 0,
        "emails": [dict(r) for r in rows],
    }
