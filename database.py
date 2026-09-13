
import sqlite3
import os
from datetime import datetime

DATABASE = os.path.join(os.path.dirname(__file__), "instance", "queries.db")

# ── Customizable Categories & Priorities ──────────────────────────
CATEGORIES = [
    "Process & Policy",
    "Tools & Systems",
    "Customer Handling",
    "Escalation Workflow",
    "Product / Warranty",
    "Compliance & Audit",
    "Training & Onboarding",
    "General / Other",
]

PRIORITIES = ["Low", "Medium", "High", "Critical"]

STATUSES = ["Open", "In Progress", "Resolved"]


# ── Database Initialization ───────────────────────────────────────
def get_db():
    """Return a new database connection with Row factory."""
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS queries (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            submitted_by    TEXT    NOT NULL,
            category        TEXT    NOT NULL,
            subject         TEXT    NOT NULL,
            description     TEXT    NOT NULL,
            tags            TEXT    DEFAULT '',
            priority        TEXT    DEFAULT 'Medium',
            status          TEXT    DEFAULT 'Open',
            advisor_response TEXT   DEFAULT '',
            reference_links TEXT    DEFAULT '',
            created_at      TEXT    NOT NULL,
            updated_at      TEXT    NOT NULL,
            resolved_at     TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            query_id    INTEGER NOT NULL,
            author      TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (query_id) REFERENCES queries(id)
        );
    """
    )
    conn.commit()
    conn.close()


# ── CRUD — Queries ────────────────────────────────────────────────
def create_query(submitted_by, category, subject, description, tags=""):
    """Insert a new query and return its ID."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO queries
           (submitted_by, category, subject, description, tags, priority, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 'Medium', 'Open', ?, ?)""",
        (submitted_by, category, subject, description, tags, now, now),
    )
    conn.commit()
    query_id = cur.lastrowid
    conn.close()
    return query_id


def get_query(query_id):
    """Return a single query by ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,)).fetchone()
    conn.close()
    return row


def get_all_queries(status_filter=None, category_filter=None, search_term=None):
    """Return queries with optional filters."""
    conn = get_db()
    sql = "SELECT * FROM queries WHERE 1=1"
    params = []

    if status_filter and status_filter != "All":
        sql += " AND status = ?"
        params.append(status_filter)

    if category_filter and category_filter != "All":
        sql += " AND category = ?"
        params.append(category_filter)

    if search_term:
        sql += " AND (subject LIKE ? OR description LIKE ? OR tags LIKE ?)"
        wildcard = f"%{search_term}%"
        params.extend([wildcard, wildcard, wildcard])

    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_open_queries():
    """Return all Open and In Progress queries, newest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM queries WHERE status IN ('Open', 'In Progress') ORDER BY "
        "CASE priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 "
        "WHEN 'Medium' THEN 3 ELSE 4 END, created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def get_resolved_queries(category_filter=None, search_term=None):
    """Return resolved queries for the Knowledge Base."""
    conn = get_db()
    sql = "SELECT * FROM queries WHERE status = 'Resolved'"
    params = []

    if category_filter and category_filter != "All":
        sql += " AND category = ?"
        params.append(category_filter)

    if search_term:
        sql += " AND (subject LIKE ? OR description LIKE ? OR tags LIKE ? OR advisor_response LIKE ?)"
        wildcard = f"%{search_term}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    sql += " ORDER BY resolved_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def update_query_response(query_id, advisor_response, priority, reference_links, status):
    """Advisor updates a query — response, priority, links, status."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resolved_at = now if status == "Resolved" else ""
    conn = get_db()
    conn.execute(
        """UPDATE queries
           SET advisor_response = ?, priority = ?, reference_links = ?,
               status = ?, updated_at = ?, resolved_at = ?
           WHERE id = ?""",
        (advisor_response, priority, reference_links, status, now, resolved_at, query_id),
    )
    conn.commit()
    conn.close()


# ── CRUD — Comments (Follow-up Thread) ───────────────────────────
def add_comment(query_id, author, message):
    """Add a follow-up comment to a query."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    conn.execute(
        "INSERT INTO comments (query_id, author, message, created_at) VALUES (?, ?, ?, ?)",
        (query_id, author, message, now),
    )
    conn.commit()
    conn.close()


def get_comments(query_id):
    """Return all comments for a query."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM comments WHERE query_id = ? ORDER BY created_at ASC",
        (query_id,),
    ).fetchall()
    conn.close()
    return rows


# ── Analytics — Refresher Reports ────────────────────────────────
def get_category_stats():
    """Count of queries per category, split by status."""
    conn = get_db()
    rows = conn.execute(
        """SELECT category, status, COUNT(*) as cnt
           FROM queries GROUP BY category, status ORDER BY category"""
    ).fetchall()
    conn.close()
    return rows


def get_high_priority_open():
    """Return open High/Critical queries."""
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM queries
           WHERE status IN ('Open', 'In Progress') AND priority IN ('High', 'Critical')
           ORDER BY CASE priority WHEN 'Critical' THEN 1 ELSE 2 END, created_at ASC"""
    ).fetchall()
    conn.close()
    return rows


def get_recurring_tags(limit=15):
    """Return most frequently used tags across all queries."""
    conn = get_db()
    rows = conn.execute("SELECT tags FROM queries WHERE tags != ''").fetchall()
    conn.close()

    tag_count = {}
    for row in rows:
        for tag in row["tags"].split(","):
            tag = tag.strip().lower()
            if tag:
                tag_count[tag] = tag_count.get(tag, 0) + 1

    sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
    return sorted_tags[:limit]


def get_summary_stats():
    """Overall stats for the refresher report header."""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM queries").fetchone()["c"]
    open_q = conn.execute("SELECT COUNT(*) as c FROM queries WHERE status = 'Open'").fetchone()["c"]
    in_prog = conn.execute("SELECT COUNT(*) as c FROM queries WHERE status = 'In Progress'").fetchone()["c"]
    resolved = conn.execute("SELECT COUNT(*) as c FROM queries WHERE status = 'Resolved'").fetchone()["c"]
    conn.close()
    return {"total": total, "open": open_q, "in_progress": in_prog, "resolved": resolved}

