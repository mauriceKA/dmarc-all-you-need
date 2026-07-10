"""Thin wrapper around imaplib for fetching report mails.

Kept deliberately small so sync.py can be tested against a stub with the
same interface. Connections are always TLS with certificate verification
(ssl.create_default_context); there is no plaintext option.
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import ssl
from email.message import Message

from .config import ImapConfig


class ImapError(Exception):
    """Raised when the IMAP server misbehaves or a command fails."""


class ImapClient:
    def __init__(self, config: ImapConfig):
        self._config = config
        self._conn: imaplib.IMAP4_SSL | None = None
        self.uidvalidity: int = 0

    # -- context manager -------------------------------------------------

    def __enter__(self) -> ImapClient:
        self.connect()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> None:
        cfg = self._config
        try:
            conn = imaplib.IMAP4_SSL(
                cfg.host, cfg.port, ssl_context=ssl.create_default_context()
            )
            conn.login(cfg.username, cfg.password)
            status, data = conn.select(self._quote_mailbox(cfg.mailbox), readonly=False)
            if status != "OK":
                raise ImapError(f"cannot select mailbox {cfg.mailbox!r}: {status}")
            status, data = conn.status(self._quote_mailbox(cfg.mailbox), "(UIDVALIDITY)")
            if status != "OK" or not data or data[0] is None:
                raise ImapError("server did not report UIDVALIDITY")
            self.uidvalidity = int(data[0].split(b"UIDVALIDITY")[1].strip(b" ()"))
        except (imaplib.IMAP4.error, OSError, ssl.SSLError) as exc:
            raise ImapError(f"IMAP connection failed: {exc}") from exc
        self._conn = conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
                self._conn.logout()
            except (imaplib.IMAP4.error, OSError):
                pass  # best-effort teardown
            self._conn = None

    # -- operations -------------------------------------------------------

    def list_uids(self) -> list[int]:
        """UIDs of all messages in the selected mailbox, oldest first."""
        status, data = self._require_conn().uid("SEARCH", None, "ALL")
        if status != "OK":
            raise ImapError(f"UID SEARCH failed: {status}")
        if not data or not data[0]:
            return []
        return [int(uid) for uid in data[0].split()]

    def fetch_message(self, uid: int) -> Message | None:
        """Fetch one full message; None if it vanished meanwhile."""
        status, data = self._require_conn().uid("FETCH", str(uid), "(BODY.PEEK[])")
        if status != "OK":
            raise ImapError(f"UID FETCH {uid} failed: {status}")
        for item in data or []:
            if isinstance(item, tuple) and len(item) >= 2:
                return email.message_from_bytes(item[1], policy=email.policy.default)
        return None

    def delete_message(self, uid: int) -> None:
        conn = self._require_conn()
        status, _ = conn.uid("STORE", str(uid), "+FLAGS", r"(\Deleted)")
        if status != "OK":
            raise ImapError(f"UID STORE {uid} failed: {status}")

    def expunge(self) -> None:
        self._require_conn().expunge()

    # -- helpers ----------------------------------------------------------

    def _require_conn(self) -> imaplib.IMAP4_SSL:
        if self._conn is None:
            raise ImapError("not connected")
        return self._conn

    @staticmethod
    def _quote_mailbox(name: str) -> str:
        return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'
