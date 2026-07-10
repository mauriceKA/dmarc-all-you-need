"""Parse IMAP BODYSTRUCTURE responses to spot report attachments cheaply.

BODYSTRUCTURE describes a message's MIME tree (content types, filenames,
sizes) without transferring the body. The sync uses it to decide which
messages are worth downloading at all — in a general-purpose mailbox with
thousands of mails, only the few with report-shaped attachments get a full
fetch.

Everything here fails OPEN: if a response cannot be parsed, the message is
treated as a candidate and downloaded, so an exotic server response can
cost bandwidth but never lose a report.
"""

from __future__ import annotations

import re
from typing import Any

# content types that plausibly carry an aggregate report (mirrors report_parser)
_REPORT_TYPES = {
    ("application", "gzip"),
    ("application", "x-gzip"),
    ("application", "zip"),
    ("application", "x-zip-compressed"),
    ("application", "xml"),
    ("text", "xml"),
}
_REPORT_SUFFIXES = (".xml", ".xml.gz", ".gz", ".zip", ".xml.zip")

_LITERAL_MARKER = re.compile(rb"\{\d+\}\s*$")


# --------------------------------------------------------------- tokenizer

def _tokenize(data: bytes) -> list[tuple[str, str]]:
    """Split an IMAP parenthesized list into (kind, value) tokens.

    kind is 'punct' for parentheses, 'str' for quoted strings, 'atom' for
    everything else (atoms keep NIL/number semantics for the parser).
    """
    tokens: list[tuple[str, str]] = []
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c in b" \r\n\t":
            i += 1
        elif c in b"()":
            tokens.append(("punct", chr(c)))
            i += 1
        elif c == ord('"'):
            out = bytearray()
            i += 1
            while i < n and data[i] != ord('"'):
                if data[i] == ord("\\") and i + 1 < n:
                    i += 1
                out.append(data[i])
                i += 1
            i += 1  # closing quote
            tokens.append(("str", out.decode("utf-8", "replace")))
        else:
            j = i
            while j < n and data[j] not in b' ()"\r\n\t':
                j += 1
            tokens.append(("atom", data[i:j].decode("ascii", "replace")))
            i = j
    return tokens


def _parse_items(tokens: list[tuple[str, str]]) -> list[Any]:
    """Parse a token stream into nested Python lists / str / int / None."""
    pos = 0

    def parse_one() -> Any:
        nonlocal pos
        kind, value = tokens[pos]
        pos += 1
        if kind == "punct" and value == "(":
            items = []
            while pos < len(tokens) and tokens[pos] != ("punct", ")"):
                items.append(parse_one())
            if pos >= len(tokens):
                raise ValueError("unbalanced parenthesis in IMAP response")
            pos += 1  # consume ')'
            return items
        if kind == "punct":  # stray ')'
            raise ValueError("unexpected ')' in IMAP response")
        if kind == "atom":
            if value.upper() == "NIL":
                return None
            if value.isdigit():
                return int(value)
        return value

    items = []
    while pos < len(tokens):
        items.append(parse_one())
    return items


def _flatten_fetch_data(data: list[Any]) -> bytes:
    """Join imaplib fetch response items into one parseable byte string.

    imaplib represents string literals as (prefix_with_size_marker, literal)
    tuples; the literal is re-inlined as a quoted string.
    """
    buffer = bytearray()
    for item in data or []:
        if item is None:
            continue
        parts = item if isinstance(item, tuple) else (item,)
        for index, part in enumerate(parts):
            if not isinstance(part, bytes):
                continue
            if isinstance(item, tuple) and index % 2 == 1:
                # a literal: inline it as a quoted string
                escaped = part.replace(b"\\", b"\\\\").replace(b'"', b'\\"')
                buffer += b'"' + escaped + b'"'
            else:
                buffer += _LITERAL_MARKER.sub(b"", part)
        buffer += b" "
    return bytes(buffer)


# ----------------------------------------------------------------- public

def parse_fetch_response(data: list[Any]) -> dict[int, list[Any]]:
    """Extract {uid: bodystructure} from a UID FETCH (BODYSTRUCTURE) response.

    Messages whose response cannot be parsed are simply absent from the
    result — callers treat them as download candidates (fail open).
    """
    try:
        items = _parse_items(_tokenize(_flatten_fetch_data(data)))
    except (ValueError, IndexError):
        return {}

    structures: dict[int, list[Any]] = {}
    for item in items:
        if not isinstance(item, list):
            continue
        uid: int | None = None
        structure: list[Any] | None = None
        for index, element in enumerate(item[:-1]):
            if not isinstance(element, str):
                continue
            key = element.upper()
            following = item[index + 1]
            if key == "UID" and isinstance(following, int):
                uid = following
            elif key == "BODYSTRUCTURE" and isinstance(following, list):
                structure = following
        if uid is not None and structure is not None:
            structures[uid] = structure
    return structures


def has_report_attachment(structure: list[Any]) -> bool:
    """True if any MIME leaf looks like it could carry an aggregate report."""
    for leaf in _leaves(structure):
        if len(leaf) >= 2 and isinstance(leaf[0], str) and isinstance(leaf[1], str):
            if (leaf[0].lower(), leaf[1].lower()) in _REPORT_TYPES:
                return True
        if any(name.lower().endswith(_REPORT_SUFFIXES) for name in _filenames(leaf)):
            return True
    return False


def _leaves(node: Any):
    """Yield the single-part leaves of a (possibly nested multipart) structure."""
    if not isinstance(node, list) or not node:
        return
    if isinstance(node[0], list):  # multipart: child parts lead, subtype follows
        for child in node:
            if isinstance(child, list):
                yield from _leaves(child)
            else:
                break
    else:
        yield node


def _filenames(leaf: list[Any]):
    """Collect NAME/FILENAME parameter values anywhere in a leaf part."""

    def scan(node: Any):
        if not isinstance(node, list):
            return
        for index, element in enumerate(node[:-1]):
            if (
                isinstance(element, str)
                # RFC 2231 encoded/continued params appear as NAME*, FILENAME*0 ...
                and element.upper().split("*")[0] in ("NAME", "FILENAME")
                and isinstance(node[index + 1], str)
            ):
                yield node[index + 1]
        for element in node:
            yield from scan(element)

    yield from scan(leaf)
