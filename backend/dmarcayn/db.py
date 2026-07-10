"""SQLite persistence: schema, connections, import transaction, read queries.

Connections are per-thread (sqlite3 objects must not cross threads). The
poller thread is the only writer; HTTP request threads only read, so WAL
mode keeps them from ever blocking each other.
"""

from __future__ import annotations

import gzip
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import Report

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY,
    domain        TEXT    NOT NULL,
    org_name      TEXT    NOT NULL,
    org_email     TEXT,
    report_id     TEXT    NOT NULL,
    date_begin    INTEGER NOT NULL,
    date_end      INTEGER NOT NULL,
    policy_adkim  TEXT,
    policy_aspf   TEXT,
    policy_p      TEXT,
    policy_sp     TEXT,
    policy_pct    INTEGER,
    raw_xml       BLOB,
    imported_at   INTEGER NOT NULL DEFAULT (unixepoch()),
    UNIQUE (org_name, report_id)
);

CREATE TABLE IF NOT EXISTS records (
    id             INTEGER PRIMARY KEY,
    report_id      INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    domain         TEXT    NOT NULL,
    date_begin     INTEGER NOT NULL,
    source_ip      TEXT    NOT NULL,
    count          INTEGER NOT NULL,
    disposition    TEXT    NOT NULL,
    eval_dkim      TEXT    NOT NULL,
    eval_spf       TEXT    NOT NULL,
    dmarc_pass     INTEGER NOT NULL,
    reason_type    TEXT,
    reason_comment TEXT,
    header_from    TEXT,
    envelope_from  TEXT,
    envelope_to    TEXT
);

CREATE TABLE IF NOT EXISTS auth_results (
    id         INTEGER PRIMARY KEY,
    record_id  INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    auth_type  TEXT    NOT NULL CHECK (auth_type IN ('dkim','spf')),
    domain     TEXT,
    selector   TEXT,
    scope      TEXT,
    result     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_messages (
    id           INTEGER PRIMARY KEY,
    uidvalidity  INTEGER NOT NULL,
    uid          INTEGER NOT NULL,
    message_id   TEXT,
    processed_at INTEGER NOT NULL DEFAULT (unixepoch()),
    status       TEXT    NOT NULL,
    detail       TEXT,
    UNIQUE (uidvalidity, uid)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_records_domain_time ON records(domain, date_begin);
CREATE INDEX IF NOT EXISTS idx_records_source      ON records(domain, source_ip);
CREATE INDEX IF NOT EXISTS idx_records_report      ON records(report_id);
CREATE INDEX IF NOT EXISTS idx_reports_domain_time ON reports(domain, date_begin);
CREATE INDEX IF NOT EXISTS idx_auth_record         ON auth_results(record_id);
CREATE INDEX IF NOT EXISTS idx_procmsg_message_id  ON processed_messages(message_id);
"""

_INTERVALS = {"day": 86_400, "week": 7 * 86_400}


class Database:
    """Thread-safe facade over one SQLite file (per-thread connections)."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._local = threading.local()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO NOTHING",
                (str(SCHEMA_VERSION),),
            )

    def connection(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._path, timeout=5.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ------------------------------------------------------------- writes

    def import_report(self, report: Report) -> bool:
        """Insert a parsed report; returns False if it was a duplicate.

        Everything (report, records, auth_results) is one transaction.
        """
        conn = self.connection()
        with conn:
            cur = conn.execute(
                """INSERT INTO reports (domain, org_name, org_email, report_id,
                       date_begin, date_end, policy_adkim, policy_aspf,
                       policy_p, policy_sp, policy_pct, raw_xml)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT (org_name, report_id) DO NOTHING""",
                (
                    report.domain,
                    report.org_name,
                    report.org_email,
                    report.report_id,
                    report.date_begin,
                    report.date_end,
                    report.policy_adkim,
                    report.policy_aspf,
                    report.policy_p,
                    report.policy_sp,
                    report.policy_pct,
                    gzip.compress(report.raw_xml),
                ),
            )
            if cur.rowcount == 0:
                return False
            report_row_id = cur.lastrowid
            for record in report.records:
                cur = conn.execute(
                    """INSERT INTO records (report_id, domain, date_begin, source_ip,
                           count, disposition, eval_dkim, eval_spf, dmarc_pass,
                           reason_type, reason_comment, header_from,
                           envelope_from, envelope_to)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        report_row_id,
                        report.domain,
                        report.date_begin,
                        record.source_ip,
                        record.count,
                        record.disposition,
                        record.eval_dkim,
                        record.eval_spf,
                        int(record.dmarc_pass),
                        record.reason_type,
                        record.reason_comment,
                        record.header_from,
                        record.envelope_from,
                        record.envelope_to,
                    ),
                )
                record_row_id = cur.lastrowid
                conn.executemany(
                    """INSERT INTO auth_results (record_id, auth_type, domain,
                           selector, scope, result)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (record_row_id, a.auth_type, a.domain, a.selector, a.scope, a.result)
                        for a in record.auth_results
                    ],
                )
        return True

    def is_message_processed(self, uidvalidity: int, uid: int) -> bool:
        row = self.connection().execute(
            "SELECT 1 FROM processed_messages WHERE uidvalidity = ? AND uid = ?",
            (uidvalidity, uid),
        ).fetchone()
        return row is not None

    def mark_message_processed(
        self,
        uidvalidity: int,
        uid: int,
        message_id: str | None,
        status: str,
        detail: str | None = None,
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO processed_messages (uidvalidity, uid, message_id, status, detail)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT (uidvalidity, uid) DO UPDATE
                       SET status = excluded.status, detail = excluded.detail""",
                (uidvalidity, uid, message_id, status, detail),
            )

    def set_meta(self, key: str, value: str) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        row = self.connection().execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # -------------------------------------------------------------- reads

    def domains(self) -> list[dict[str, Any]]:
        rows = self.connection().execute(
            """SELECT r.domain,
                      COUNT(*)                       AS report_count,
                      COALESCE(SUM(m.messages), 0)   AS message_count,
                      MIN(r.date_begin)              AS first_seen,
                      MAX(r.date_end)                AS last_seen
               FROM reports r
               LEFT JOIN (SELECT report_id, SUM(count) AS messages
                          FROM records GROUP BY report_id) m ON m.report_id = r.id
               GROUP BY r.domain
               ORDER BY r.domain"""
        ).fetchall()
        return [dict(row) for row in rows]

    def summary(self, domain: str, from_ts: int, to_ts: int) -> dict[str, Any]:
        conn = self.connection()
        row = conn.execute(
            """SELECT COALESCE(SUM(count), 0)                                    AS total_messages,
                      COALESCE(SUM(CASE WHEN dmarc_pass = 1 THEN count END), 0)  AS dmarc_pass,
                      COALESCE(SUM(CASE WHEN eval_dkim = 'pass' THEN count END), 0) AS dkim_pass,
                      COALESCE(SUM(CASE WHEN eval_spf  = 'pass' THEN count END), 0) AS spf_pass,
                      COALESCE(SUM(CASE WHEN disposition = 'none'       THEN count END), 0) AS disp_none,
                      COALESCE(SUM(CASE WHEN disposition = 'quarantine' THEN count END), 0) AS disp_quarantine,
                      COALESCE(SUM(CASE WHEN disposition = 'reject'     THEN count END), 0) AS disp_reject,
                      COUNT(DISTINCT source_ip)                                  AS distinct_sources,
                      COUNT(DISTINCT report_id)                                  AS report_count
               FROM records
               WHERE domain = ? AND date_begin BETWEEN ? AND ?""",
            (domain, from_ts, to_ts),
        ).fetchone()
        return {
            "total_messages": row["total_messages"],
            "dmarc_pass": row["dmarc_pass"],
            "dmarc_fail": row["total_messages"] - row["dmarc_pass"],
            "dkim_pass": row["dkim_pass"],
            "spf_pass": row["spf_pass"],
            "dispositions": {
                "none": row["disp_none"],
                "quarantine": row["disp_quarantine"],
                "reject": row["disp_reject"],
            },
            "distinct_sources": row["distinct_sources"],
            "report_count": row["report_count"],
        }

    def timeseries(
        self, domain: str, from_ts: int, to_ts: int, interval: str = "day"
    ) -> list[dict[str, Any]]:
        bucket = _INTERVALS.get(interval)
        if bucket is None:
            raise ValueError(f"invalid interval: {interval!r}")
        rows = self.connection().execute(
            f"""SELECT (date_begin / {bucket}) * {bucket} AS bucket,
                       COALESCE(SUM(CASE WHEN dmarc_pass = 1 THEN count END), 0) AS pass,
                       COALESCE(SUM(CASE WHEN dmarc_pass = 0 THEN count END), 0) AS fail,
                       COALESCE(SUM(CASE WHEN disposition = 'quarantine' THEN count END), 0)
                           AS quarantine,
                       COALESCE(SUM(CASE WHEN disposition = 'reject' THEN count END), 0) AS reject
                FROM records
                WHERE domain = ? AND date_begin BETWEEN ? AND ?
                GROUP BY bucket
                ORDER BY bucket""",  # noqa: S608 -- bucket is whitelisted above, not user input
            (domain, from_ts, to_ts),
        ).fetchall()
        return [dict(row) for row in rows]

    def alignment(self, domain: str, from_ts: int, to_ts: int) -> list[dict[str, Any]]:
        rows = self.connection().execute(
            """SELECT eval_dkim AS dkim, eval_spf AS spf, COALESCE(SUM(count), 0) AS count
               FROM records
               WHERE domain = ? AND date_begin BETWEEN ? AND ?
               GROUP BY eval_dkim, eval_spf
               ORDER BY count DESC""",
            (domain, from_ts, to_ts),
        ).fetchall()
        return [dict(row) for row in rows]

    def sources(
        self, domain: str, from_ts: int, to_ts: int, limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        conn = self.connection()
        total_rows = conn.execute(
            """SELECT COUNT(DISTINCT source_ip) AS n FROM records
               WHERE domain = ? AND date_begin BETWEEN ? AND ?""",
            (domain, from_ts, to_ts),
        ).fetchone()["n"]
        rows = conn.execute(
            """SELECT source_ip,
                      SUM(count)                                                AS total,
                      COALESCE(SUM(CASE WHEN dmarc_pass = 1 THEN count END), 0) AS pass,
                      COALESCE(SUM(CASE WHEN dmarc_pass = 0 THEN count END), 0) AS fail,
                      COALESCE(SUM(CASE WHEN disposition = 'quarantine' THEN count END), 0)
                          AS quarantine,
                      COALESCE(SUM(CASE WHEN disposition = 'reject' THEN count END), 0) AS reject,
                      MAX(date_begin)                                           AS last_seen
               FROM records
               WHERE domain = ? AND date_begin BETWEEN ? AND ?
               GROUP BY source_ip
               ORDER BY total DESC, source_ip
               LIMIT ? OFFSET ?""",
            (domain, from_ts, to_ts, int(limit), int(offset)),
        ).fetchall()
        return {"total_rows": total_rows, "sources": [dict(row) for row in rows]}

    def reports(
        self, domain: str, from_ts: int, to_ts: int, limit: int = 50, offset: int = 0
    ) -> dict[str, Any]:
        conn = self.connection()
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM reports WHERE domain = ? AND date_begin BETWEEN ? AND ?",
            (domain, from_ts, to_ts),
        ).fetchone()["n"]
        rows = conn.execute(
            """SELECT r.id, r.org_name, r.report_id, r.date_begin, r.date_end,
                      COALESCE(m.messages, 0)   AS message_count,
                      COALESCE(m.fail_count, 0) AS fail_count
               FROM reports r
               LEFT JOIN (SELECT report_id,
                                 SUM(count) AS messages,
                                 SUM(CASE WHEN dmarc_pass = 0 THEN count ELSE 0 END) AS fail_count
                          FROM records GROUP BY report_id) m ON m.report_id = r.id
               WHERE r.domain = ? AND r.date_begin BETWEEN ? AND ?
               ORDER BY r.date_begin DESC, r.id DESC
               LIMIT ? OFFSET ?""",
            (domain, from_ts, to_ts, int(limit), int(offset)),
        ).fetchall()
        return {"total": total, "reports": [dict(row) for row in rows]}

    def report_detail(self, report_row_id: int) -> dict[str, Any] | None:
        conn = self.connection()
        report = conn.execute(
            """SELECT id, domain, org_name, org_email, report_id, date_begin, date_end,
                      policy_adkim, policy_aspf, policy_p, policy_sp, policy_pct, imported_at
               FROM reports WHERE id = ?""",
            (report_row_id,),
        ).fetchone()
        if report is None:
            return None
        records = conn.execute(
            """SELECT id, source_ip, count, disposition, eval_dkim, eval_spf, dmarc_pass,
                      reason_type, reason_comment, header_from, envelope_from, envelope_to
               FROM records WHERE report_id = ? ORDER BY count DESC, id""",
            (report_row_id,),
        ).fetchall()
        record_ids = [row["id"] for row in records]
        auth_by_record: dict[int, list[dict[str, Any]]] = {rid: [] for rid in record_ids}
        if record_ids:
            placeholders = ",".join("?" * len(record_ids))
            auth_rows = conn.execute(
                f"""SELECT record_id, auth_type, domain, selector, scope, result
                    FROM auth_results WHERE record_id IN ({placeholders})
                    ORDER BY id""",  # noqa: S608 -- placeholders are literal '?' marks
                record_ids,
            ).fetchall()
            for row in auth_rows:
                auth_by_record[row["record_id"]].append(
                    {k: row[k] for k in ("auth_type", "domain", "selector", "scope", "result")}
                )
        return {
            **dict(report),
            "records": [
                {**dict(rec), "auth_results": auth_by_record[rec["id"]]} for rec in records
            ],
        }
