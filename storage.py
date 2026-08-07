"""
Lightweight SQLite storage for signal history and results.

Since trades are executed manually, the bot can't know the outcome on
its own - you report it back with /result win or /result loss after
each trade resolves, and this module tracks it so /stats can show
real accuracy per pair and per confidence tier.
"""
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Optional

DB_PATH = "signals.db"


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with closing(_connect()) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pair TEXT NOT NULL,
                direction TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                tier TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                outcome TEXT DEFAULT NULL,
                resolved_at TEXT DEFAULT NULL
            )
        """)


def save_signal(pair: str, direction: str, confidence: int, tier: str, entry_time: datetime) -> int:
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO signals (pair, direction, confidence, tier, entry_time, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pair, direction, confidence, tier, entry_time.isoformat(), datetime.now().isoformat()),
        )
        return cur.lastrowid


def get_last_unresolved_signal_id() -> Optional[int]:
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT id FROM signals WHERE outcome IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None


def resolve_signal(signal_id: int, outcome: str) -> bool:
    """outcome should be 'win' or 'loss'."""
    with closing(_connect()) as conn, conn:
        cur = conn.execute(
            "UPDATE signals SET outcome = ?, resolved_at = ? WHERE id = ? AND outcome IS NULL",
            (outcome, datetime.now().isoformat(), signal_id),
        )
        return cur.rowcount > 0


def get_stats():
    """Returns overall + per-pair + per-tier win/loss breakdown."""
    with closing(_connect()) as conn:
        overall = conn.execute(
            "SELECT outcome, COUNT(*) FROM signals WHERE outcome IS NOT NULL GROUP BY outcome"
        ).fetchall()

        per_pair = conn.execute(
            "SELECT pair, outcome, COUNT(*) FROM signals WHERE outcome IS NOT NULL "
            "GROUP BY pair, outcome"
        ).fetchall()

        per_tier = conn.execute(
            "SELECT tier, outcome, COUNT(*) FROM signals WHERE outcome IS NOT NULL "
            "GROUP BY tier, outcome"
        ).fetchall()

        pending = conn.execute(
            "SELECT COUNT(*) FROM signals WHERE outcome IS NULL"
        ).fetchone()[0]

    return {
        "overall": dict(overall),
        "per_pair": per_pair,
        "per_tier": per_tier,
        "pending": pending,
    }
