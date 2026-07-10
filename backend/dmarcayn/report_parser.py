"""Extract and parse DMARC aggregate reports from mail messages.

Everything handled here is untrusted third-party input:
- XML is parsed exclusively with defusedxml (XXE / entity-expansion safe).
- gzip payloads are stream-decompressed with a hard output cap.
- zip archives must contain exactly one member, whose claimed size is
  ignored; the member is stream-read against the same cap, in memory only.
"""

from __future__ import annotations

import io
import zipfile
import zlib
from email.message import Message

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from .models import AuthResult, Report, ReportRecord

_CHUNK = 64 * 1024

# Attachment content types seen in the wild for aggregate reports.
_REPORT_CONTENT_TYPES = {
    "application/gzip",
    "application/x-gzip",
    "application/zip",
    "application/x-zip-compressed",
    "application/xml",
    "text/xml",
    "application/octet-stream",  # decided by filename
}
_REPORT_SUFFIXES = (".xml", ".xml.gz", ".gz", ".zip", ".xml.zip")


class ReportParseError(Exception):
    """Raised when an attachment cannot be safely turned into a report."""


def _decompress_gzip(data: bytes, max_bytes: int) -> bytes:
    """Stream-decompress gzip data, refusing to produce more than max_bytes."""
    decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16)  # gzip framing
    out = bytearray()
    try:
        pos = 0
        while pos < len(data):
            chunk = decompressor.decompress(data[pos : pos + _CHUNK], max_bytes + 1 - len(out))
            out += chunk
            if len(out) > max_bytes:
                raise ReportParseError(f"gzip payload exceeds {max_bytes} bytes decompressed")
            if decompressor.unconsumed_tail:
                # output cap reached with input left over
                raise ReportParseError(f"gzip payload exceeds {max_bytes} bytes decompressed")
            pos += _CHUNK
        out += decompressor.flush()
    except zlib.error as exc:
        raise ReportParseError(f"corrupt gzip data: {exc}") from exc
    if len(out) > max_bytes:
        raise ReportParseError(f"gzip payload exceeds {max_bytes} bytes decompressed")
    return bytes(out)


def _extract_zip(data: bytes, max_bytes: int) -> bytes:
    """Read the single member of a zip archive, capped, entirely in memory."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            if len(names) != 1:
                raise ReportParseError(
                    f"zip archive must contain exactly one file, found {len(names)}"
                )
            name = names[0]
            if name.lower().endswith((".zip", ".gz")):
                raise ReportParseError("nested archives are not allowed")
            out = bytearray()
            with archive.open(name) as member:  # claimed sizes are ignored: we count bytes
                while True:
                    chunk = member.read(_CHUNK)
                    if not chunk:
                        break
                    out += chunk
                    if len(out) > max_bytes:
                        raise ReportParseError(
                            f"zip member exceeds {max_bytes} bytes decompressed"
                        )
            return bytes(out)
    except zipfile.BadZipFile as exc:
        raise ReportParseError(f"corrupt zip data: {exc}") from exc


def extract_report_xml(
    payload: bytes, filename: str, max_attachment_bytes: int, max_decompressed_bytes: int
) -> bytes:
    """Turn a raw attachment into report XML bytes, defusing size tricks."""
    if len(payload) > max_attachment_bytes:
        raise ReportParseError(f"attachment exceeds {max_attachment_bytes} bytes")
    name = filename.lower()
    if payload[:2] == b"\x1f\x8b":  # gzip magic
        return _decompress_gzip(payload, max_decompressed_bytes)
    if payload[:4] == b"PK\x03\x04":  # zip magic
        return _extract_zip(payload, max_decompressed_bytes)
    if name.endswith(".xml") or payload.lstrip()[:1] == b"<":
        if len(payload) > max_decompressed_bytes:
            raise ReportParseError(f"XML exceeds {max_decompressed_bytes} bytes")
        return payload
    raise ReportParseError(f"unrecognized attachment format: {filename!r}")


def _looks_like_report_attachment(part: Message) -> bool:
    content_type = part.get_content_type()
    filename = (part.get_filename() or "").lower()
    if content_type in ("application/xml", "text/xml"):
        return True
    if content_type in _REPORT_CONTENT_TYPES:
        return filename.endswith(_REPORT_SUFFIXES) if filename else True
    return filename.endswith(_REPORT_SUFFIXES)


def find_report_attachments(message: Message) -> list[tuple[str, bytes]]:
    """Return (filename, payload) for every plausible report attachment."""
    attachments = []
    for part in message.walk():
        if part.is_multipart():
            continue
        if not _looks_like_report_attachment(part):
            continue
        payload = part.get_payload(decode=True)
        if payload:
            attachments.append((part.get_filename() or "report", payload))
    return attachments


def _text(element, path: str) -> str | None:
    node = element.find(path)
    if node is None or node.text is None:
        return None
    value = node.text.strip()
    return value or None


def _required(element, path: str, context: str) -> str:
    value = _text(element, path)
    if value is None:
        raise ReportParseError(f"report is missing required element {context}/{path}")
    return value


def _epoch(element, path: str, context: str) -> int:
    raw = _required(element, path, context)
    try:
        return int(float(raw))  # some reporters send floats
    except ValueError:
        raise ReportParseError(f"invalid timestamp in {context}/{path}: {raw!r}") from None


def _int_or_none(element, path: str) -> int | None:
    raw = _text(element, path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_record(node) -> ReportRecord:
    row = node.find("row")
    if row is None:
        raise ReportParseError("record is missing <row>")
    policy = row.find("policy_evaluated")
    if policy is None:
        raise ReportParseError("record is missing <policy_evaluated>")

    count_raw = _required(row, "count", "record/row")
    try:
        count = int(count_raw)
    except ValueError:
        raise ReportParseError(f"invalid record count: {count_raw!r}") from None
    if count < 0:
        raise ReportParseError(f"negative record count: {count}")

    identifiers = node.find("identifiers")
    auth = node.find("auth_results")
    auth_results: list[AuthResult] = []
    if auth is not None:
        for dkim in auth.findall("dkim"):
            auth_results.append(
                AuthResult(
                    auth_type="dkim",
                    domain=_text(dkim, "domain"),
                    selector=_text(dkim, "selector"),
                    result=_text(dkim, "result") or "none",
                )
            )
        for spf in auth.findall("spf"):
            auth_results.append(
                AuthResult(
                    auth_type="spf",
                    domain=_text(spf, "domain"),
                    scope=_text(spf, "scope"),
                    result=_text(spf, "result") or "none",
                )
            )

    reason = policy.find("reason")
    return ReportRecord(
        source_ip=_required(row, "source_ip", "record/row"),
        count=count,
        disposition=(_text(policy, "disposition") or "none").lower(),
        eval_dkim=(_text(policy, "dkim") or "fail").lower(),
        eval_spf=(_text(policy, "spf") or "fail").lower(),
        header_from=(_text(identifiers, "header_from") or "").lower() or None
        if identifiers is not None
        else None,
        envelope_from=_text(identifiers, "envelope_from") if identifiers is not None else None,
        envelope_to=_text(identifiers, "envelope_to") if identifiers is not None else None,
        reason_type=_text(reason, "type") if reason is not None else None,
        reason_comment=_text(reason, "comment") if reason is not None else None,
        auth_results=tuple(auth_results),
    )


def parse_report_xml(xml_bytes: bytes) -> Report:
    """Parse RFC 7489 aggregate report XML into a Report. Raises ReportParseError."""
    try:
        root = SafeET.fromstring(xml_bytes)
    except DefusedXmlException as exc:
        raise ReportParseError(
            f"rejected dangerous XML construct: {exc.__class__.__name__}"
        ) from exc
    except SafeET.ParseError as exc:
        raise ReportParseError(f"malformed XML: {exc}") from exc

    if root.tag != "feedback":
        raise ReportParseError(f"not a DMARC aggregate report (root element <{root.tag}>)")

    metadata = root.find("report_metadata")
    policy = root.find("policy_published")
    if metadata is None or policy is None:
        raise ReportParseError("report is missing <report_metadata> or <policy_published>")
    date_range = metadata.find("date_range")
    if date_range is None:
        raise ReportParseError("report is missing <report_metadata>/<date_range>")

    records = tuple(_parse_record(node) for node in root.findall("record"))
    if not records:
        raise ReportParseError("report contains no <record> elements")

    return Report(
        domain=_required(policy, "domain", "policy_published").lower(),
        org_name=_required(metadata, "org_name", "report_metadata"),
        org_email=_text(metadata, "email"),
        report_id=_required(metadata, "report_id", "report_metadata"),
        date_begin=_epoch(date_range, "begin", "date_range"),
        date_end=_epoch(date_range, "end", "date_range"),
        policy_adkim=_text(policy, "adkim"),
        policy_aspf=_text(policy, "aspf"),
        policy_p=_text(policy, "p"),
        policy_sp=_text(policy, "sp"),
        policy_pct=_int_or_none(policy, "pct"),
        records=records,
        raw_xml=xml_bytes,
    )


def parse_attachment(
    payload: bytes, filename: str, max_attachment_bytes: int, max_decompressed_bytes: int
) -> Report:
    """Convenience: extract_report_xml + parse_report_xml."""
    xml_bytes = extract_report_xml(
        payload, filename, max_attachment_bytes, max_decompressed_bytes
    )
    return parse_report_xml(xml_bytes)
