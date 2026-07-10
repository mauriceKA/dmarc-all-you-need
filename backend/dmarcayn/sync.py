"""One sync run: fetch mails, import their reports, track what was seen."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from email.message import Message
from typing import Protocol

from .config import Config
from .db import Database
from .report_parser import ReportParseError, find_report_attachments, parse_attachment

logger = logging.getLogger(__name__)


class MailSource(Protocol):
    """What sync needs from an IMAP client (ImapClient satisfies this)."""

    uidvalidity: int

    def list_uids(self) -> list[int]: ...
    def fetch_message(self, uid: int) -> Message | None: ...
    def delete_message(self, uid: int) -> None: ...
    def expunge(self) -> None: ...


@dataclass
class SyncResult:
    fetched: int = 0
    imported: int = 0
    duplicates: int = 0
    skipped: int = 0  # non-report mails
    errors: int = 0
    error_details: list[str] = field(default_factory=list)


def run_sync(client: MailSource, db: Database, config: Config) -> SyncResult:
    """Process every unprocessed mail in the mailbox. Never raises for a
    single bad message — parse failures are recorded and skipped."""
    result = SyncResult()
    delete_after_import = config.imap.delete_after_import
    uidvalidity = client.uidvalidity
    needs_expunge = False

    for uid in client.list_uids():
        if db.is_message_processed(uidvalidity, uid):
            continue
        result.fetched += 1

        message = client.fetch_message(uid)
        if message is None:
            continue  # deleted by another client between SEARCH and FETCH
        message_id = message.get("Message-ID")

        status, detail = _process_message(message, db, config, result)
        db.mark_message_processed(uidvalidity, uid, message_id, status, detail)

        # duplicates are safe to delete too: their content is already stored
        if delete_after_import and status in ("imported", "duplicate_report"):
            client.delete_message(uid)
            needs_expunge = True

    if needs_expunge:
        client.expunge()
    return result


def _process_message(
    message: Message, db: Database, config: Config, result: SyncResult
) -> tuple[str, str | None]:
    """Import all report attachments of one message; returns (status, detail)."""
    attachments = find_report_attachments(message)
    if not attachments:
        result.skipped += 1
        return "no_report", None

    imported_domains: list[str] = []
    duplicates = 0
    errors: list[str] = []
    for filename, payload in attachments:
        try:
            report = parse_attachment(
                payload,
                filename,
                config.limits.max_attachment_bytes,
                config.limits.max_decompressed_bytes,
            )
        except ReportParseError as exc:
            errors.append(f"{filename}: {exc}")
            continue
        if db.import_report(report):
            imported_domains.append(report.domain)
        else:
            duplicates += 1

    if imported_domains:
        result.imported += len(imported_domains)
        result.duplicates += duplicates
        return "imported", ", ".join(imported_domains)
    if duplicates:
        result.duplicates += duplicates
        return "duplicate_report", None
    result.errors += len(errors)
    result.error_details.extend(errors)
    logger.warning("failed to parse report mail: %s", "; ".join(errors))
    return "parse_error", "; ".join(errors)[:500]
