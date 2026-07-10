import gzip
import io
import zipfile
from email.message import EmailMessage
from pathlib import Path

import pytest

from dmarcayn.report_parser import (
    ReportParseError,
    extract_report_xml,
    find_report_attachments,
    parse_attachment,
    parse_report_xml,
)

FIXTURES = Path(__file__).parent / "fixtures"
REPORT_XML = (FIXTURES / "google_report.xml").read_bytes()
XXE_XML = (FIXTURES / "xxe_probe.xml").read_bytes()

MAX_ATTACHMENT = 1024 * 1024
MAX_DECOMPRESSED = 4 * 1024 * 1024


def zip_bytes(name: str, data: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, data)
    return buffer.getvalue()


# ---------------------------------------------------------------- parsing


def test_parse_full_report():
    report = parse_report_xml(REPORT_XML)
    assert report.domain == "example.com"
    assert report.org_name == "google.com"
    assert report.report_id == "17538555505881252174"
    assert report.date_begin == 1751328000
    assert report.policy_p == "quarantine"
    assert report.policy_pct == 100
    assert len(report.records) == 2

    ok, fwd = report.records
    assert ok.source_ip == "192.0.2.10"
    assert ok.count == 7
    assert ok.dmarc_pass is True
    assert {a.auth_type for a in ok.auth_results} == {"dkim", "spf"}

    assert fwd.disposition == "quarantine"
    assert fwd.dmarc_pass is False
    assert fwd.header_from == "example.com"  # lowercased
    assert fwd.reason_type == "forwarded"
    spf = next(a for a in fwd.auth_results if a.auth_type == "spf")
    assert spf.result == "softfail"
    assert spf.scope == "mfrom"


def test_xxe_probe_rejected():
    with pytest.raises(ReportParseError, match="dangerous XML|malformed XML"):
        parse_report_xml(XXE_XML)


def test_billion_laughs_rejected():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lolz ['
        b'<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;">'
        b'<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
        b"]><feedback>&lol3;</feedback>"
    )
    with pytest.raises(ReportParseError):
        parse_report_xml(bomb)


def test_malformed_xml_rejected():
    with pytest.raises(ReportParseError, match="malformed XML"):
        parse_report_xml(b"<feedback><unclosed>")


def test_wrong_root_rejected():
    with pytest.raises(ReportParseError, match="not a DMARC aggregate report"):
        parse_report_xml(b"<html/>")


def test_missing_records_rejected():
    xml = (
        b"<feedback><report_metadata><org_name>x</org_name><report_id>1</report_id>"
        b"<date_range><begin>0</begin><end>1</end></date_range></report_metadata>"
        b"<policy_published><domain>example.com</domain></policy_published></feedback>"
    )
    with pytest.raises(ReportParseError, match="no <record>"):
        parse_report_xml(xml)


def test_negative_count_rejected():
    xml = REPORT_XML.replace(b"<count>7</count>", b"<count>-7</count>")
    with pytest.raises(ReportParseError, match="negative record count"):
        parse_report_xml(xml)


# ----------------------------------------------------------- extraction


def test_extract_plain_xml():
    assert extract_report_xml(REPORT_XML, "r.xml", MAX_ATTACHMENT, MAX_DECOMPRESSED) == REPORT_XML


def test_extract_gzip():
    payload = gzip.compress(REPORT_XML)
    assert extract_report_xml(payload, "r.xml.gz", MAX_ATTACHMENT, MAX_DECOMPRESSED) == REPORT_XML


def test_extract_zip():
    payload = zip_bytes("r.xml", REPORT_XML)
    assert extract_report_xml(payload, "r.zip", MAX_ATTACHMENT, MAX_DECOMPRESSED) == REPORT_XML


def test_attachment_size_cap():
    with pytest.raises(ReportParseError, match="attachment exceeds"):
        extract_report_xml(b"x" * 100, "r.xml", 99, MAX_DECOMPRESSED)


def test_gzip_bomb_rejected():
    bomb = gzip.compress(b"\x00" * (2 * 1024 * 1024))  # 2 MiB of zeros, tiny compressed
    with pytest.raises(ReportParseError, match="exceeds .* decompressed"):
        extract_report_xml(bomb, "r.xml.gz", MAX_ATTACHMENT, 1024 * 1024)


def test_zip_bomb_rejected():
    bomb = zip_bytes("r.xml", b"\x00" * (2 * 1024 * 1024))
    with pytest.raises(ReportParseError, match="exceeds .* decompressed"):
        extract_report_xml(bomb, "r.zip", MAX_ATTACHMENT, 1024 * 1024)


def test_zip_multiple_members_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.xml", b"<a/>")
        archive.writestr("b.xml", b"<b/>")
    with pytest.raises(ReportParseError, match="exactly one file"):
        extract_report_xml(buffer.getvalue(), "r.zip", MAX_ATTACHMENT, MAX_DECOMPRESSED)


def test_zip_nested_archive_rejected():
    payload = zip_bytes("inner.zip", zip_bytes("r.xml", REPORT_XML))
    with pytest.raises(ReportParseError, match="nested archives"):
        extract_report_xml(payload, "r.zip", MAX_ATTACHMENT, MAX_DECOMPRESSED)


def test_corrupt_gzip_rejected():
    with pytest.raises(ReportParseError, match="corrupt gzip"):
        extract_report_xml(b"\x1f\x8b" + b"garbage", "r.gz", MAX_ATTACHMENT, MAX_DECOMPRESSED)


def test_unknown_format_rejected():
    with pytest.raises(ReportParseError, match="unrecognized attachment format"):
        extract_report_xml(b"not a report", "r.bin", MAX_ATTACHMENT, MAX_DECOMPRESSED)


# ------------------------------------------------------ mail attachments


def build_mail(filename: str, payload: bytes, maintype: str, subtype: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "noreply-dmarc-support@google.com"
    msg["To"] = "dmarc-reports@example.com"
    msg["Subject"] = "Report domain: example.com"
    msg["Message-ID"] = "<test@google.com>"
    msg.set_content("aggregate report attached")
    msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def test_find_and_parse_gzip_attachment():
    filename = "google.com!example.com!1751328000!1751414399.xml.gz"
    mail = build_mail(filename, gzip.compress(REPORT_XML), "application", "gzip")
    attachments = find_report_attachments(mail)
    assert [name for name, _ in attachments] == [filename]
    report = parse_attachment(attachments[0][1], filename, MAX_ATTACHMENT, MAX_DECOMPRESSED)
    assert report.domain == "example.com"


def test_find_zip_attachment_with_octet_stream_type():
    filename = "report.zip"
    mail = build_mail(filename, zip_bytes("r.xml", REPORT_XML), "application", "octet-stream")
    assert len(find_report_attachments(mail)) == 1


def test_plain_text_mail_has_no_attachments():
    msg = EmailMessage()
    msg.set_content("just words, no report")
    assert find_report_attachments(msg) == []
