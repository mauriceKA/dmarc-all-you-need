import gzip
from email.message import EmailMessage
from pathlib import Path

from dmarcayn.config import (
    Config,
    ImapConfig,
    LimitsConfig,
    ServerConfig,
    StorageConfig,
    SyncConfig,
)
from dmarcayn.sync import run_sync

FIXTURES = Path(__file__).parent / "fixtures"
REPORT_XML = (FIXTURES / "google_report.xml").read_bytes()


def make_config(delete_after_import=False):
    return Config(
        imap=ImapConfig(
            host="imap.example.com",
            port=993,
            username="u",
            password="p",
            mailbox="INBOX",
            delete_after_import=delete_after_import,
        ),
        sync=SyncConfig(poll_interval_minutes=30),
        server=ServerConfig(host="127.0.0.1", port=8080, static_dir=None),
        storage=StorageConfig(database_path=Path("unused")),
        limits=LimitsConfig(
            max_attachment_bytes=1024 * 1024, max_decompressed_bytes=4 * 1024 * 1024
        ),
    )


def report_mail(message_id="<r1@google.com>", xml=REPORT_XML):
    msg = EmailMessage()
    msg["Message-ID"] = message_id
    msg["Subject"] = "Report domain: example.com"
    msg.set_content("report attached")
    msg.add_attachment(
        gzip.compress(xml),
        maintype="application",
        subtype="gzip",
        filename="google.com!example.com!1!2.xml.gz",
    )
    return msg


def plain_mail():
    msg = EmailMessage()
    msg["Message-ID"] = "<chat@x>"
    msg.set_content("hello, no report here")
    return msg


class StubMailbox:
    """In-memory MailSource."""

    def __init__(self, messages, structures=None):
        self.uidvalidity = 7
        self.messages = dict(messages)  # uid -> Message
        self.structures = dict(structures or {})  # uid -> parsed bodystructure
        self.deleted = []
        self.downloaded = []  # uids that got a full fetch
        self.expunged = False

    def list_uids(self):
        return sorted(self.messages)

    def fetch_structures(self, uids):
        return {uid: self.structures[uid] for uid in uids if uid in self.structures}

    def fetch_message(self, uid):
        self.downloaded.append(uid)
        return self.messages.get(uid)

    def delete_message(self, uid):
        self.deleted.append(uid)

    def expunge(self):
        self.expunged = True
        for uid in self.deleted:
            self.messages.pop(uid, None)


def test_sync_imports_reports(db):
    mailbox = StubMailbox({1: report_mail(), 2: plain_mail()})
    result = run_sync(mailbox, db, make_config())
    assert result.fetched == 2
    assert result.imported == 1
    assert result.skipped == 1
    assert result.errors == 0
    assert db.domains()[0]["domain"] == "example.com"
    assert mailbox.deleted == []


def test_sync_skips_already_processed(db):
    mailbox = StubMailbox({1: report_mail()})
    run_sync(mailbox, db, make_config())
    result = run_sync(mailbox, db, make_config())
    assert result.fetched == 0
    assert db.domains()[0]["report_count"] == 1


def test_sync_marks_duplicates(db):
    # same report_id arrives in two different mails
    mailbox = StubMailbox(
        {1: report_mail("<a@google.com>"), 2: report_mail("<b@google.com>")}
    )
    result = run_sync(mailbox, db, make_config())
    assert result.imported == 1
    assert result.duplicates == 1
    assert db.domains()[0]["report_count"] == 1


def test_sync_delete_after_import(db):
    mailbox = StubMailbox(
        {
            1: report_mail("<a@google.com>"),
            2: report_mail("<b@google.com>"),  # duplicate -> also deleted
            3: plain_mail(),  # not a report -> kept
        }
    )
    result = run_sync(mailbox, db, make_config(delete_after_import=True))
    assert result.imported == 1
    assert sorted(mailbox.deleted) == [1, 2]
    assert mailbox.expunged is True
    assert list(mailbox.messages) == [3]


def test_sync_skips_downloads_via_structure_scan(db):
    # a plain-text mail whose BODYSTRUCTURE shows no report attachment
    text_structure = ["TEXT", "PLAIN", ["CHARSET", "UTF-8"], None, None, "7BIT", 100, 5]
    mailbox = StubMailbox(
        {1: plain_mail(), 2: report_mail()},
        structures={1: text_structure},
    )
    result = run_sync(mailbox, db, make_config())
    assert mailbox.downloaded == [2]  # the text mail was never fetched in full
    assert result.skipped == 1
    assert result.fetched == 1
    assert result.imported == 1
    # skipped mail is marked processed and not rescanned next time
    assert db.is_message_processed(7, 1) is True
    assert run_sync(mailbox, db, make_config()).fetched == 0


def test_sync_fails_open_without_structure(db):
    # no BODYSTRUCTURE info available -> must download to be safe
    mailbox = StubMailbox({1: plain_mail()})
    result = run_sync(mailbox, db, make_config())
    assert mailbox.downloaded == [1]
    assert result.skipped == 1  # counted as no_report after the full fetch


def test_sync_records_parse_errors_and_continues(db):
    broken = report_mail("<bad@x>", xml=b"<feedback><unclosed>")
    mailbox = StubMailbox({1: broken, 2: report_mail()})
    result = run_sync(mailbox, db, make_config())
    assert result.errors == 1
    assert result.imported == 1
    assert any("malformed XML" in detail for detail in result.error_details)
    # broken mail is marked processed and not retried
    assert db.is_message_processed(7, 1) is True
    assert run_sync(mailbox, db, make_config()).fetched == 0
