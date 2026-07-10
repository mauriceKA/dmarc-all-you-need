from dmarcayn.bodystructure import has_report_attachment, parse_fetch_response

# Realistic server responses (Gmail/Dovecot style) for UID FETCH (BODYSTRUCTURE)

ZIP_REPORT = (
    b'1 (UID 4711 BODYSTRUCTURE (("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "7BIT" 12 1)'
    b'("APPLICATION" "ZIP" ("NAME" "google.com!example.com!1751328000!1751414399.zip") NIL NIL'
    b' "BASE64" 2814 NIL ("ATTACHMENT" ("FILENAME"'
    b' "google.com!example.com!1751328000!1751414399.zip")) NIL)'
    b' "MIXED" ("BOUNDARY" "000abc") NIL NIL))'
)

PLAIN_TEXT = b'2 (UID 4712 BODYSTRUCTURE ("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "7BIT" 100 5))'

HTML_NEWSLETTER = (
    b'3 (UID 4713 BODYSTRUCTURE (("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "QUOTED-PRINTABLE"'
    b' 500 12)("TEXT" "HTML" ("CHARSET" "UTF-8") NIL NIL "QUOTED-PRINTABLE" 9000 200)'
    b' "ALTERNATIVE" ("BOUNDARY" "b1") NIL NIL))'
)

PDF_INVOICE = (
    b'4 (UID 4714 BODYSTRUCTURE (("TEXT" "PLAIN" NIL NIL NIL "7BIT" 5 1)'
    b'("APPLICATION" "PDF" ("NAME" "invoice.pdf") NIL NIL "BASE64" 90000'
    b' NIL ("ATTACHMENT" ("FILENAME" "invoice.pdf")) NIL) "MIXED" ("BOUNDARY" "b2") NIL NIL))'
)

OCTET_STREAM_GZ = (
    b'5 (UID 4715 BODYSTRUCTURE (("TEXT" "PLAIN" NIL NIL NIL "7BIT" 2 1)'
    b'("APPLICATION" "OCTET-STREAM" ("NAME" "yahoo.com!example.com!1!2.xml.gz") NIL NIL'
    b' "BASE64" 999 NIL NIL NIL) "MIXED" NIL NIL NIL))'
)

# deeply nested: report attachment inside multipart/mixed > multipart/related
NESTED_GZIP = (
    b'6 (UID 4716 BODYSTRUCTURE ((("TEXT" "PLAIN" NIL NIL NIL "7BIT" 2 1)'
    b'("TEXT" "HTML" NIL NIL NIL "7BIT" 4 1) "ALTERNATIVE" NIL NIL NIL)'
    b'("APPLICATION" "GZIP" ("NAME" "r.xml.gz") NIL NIL "BASE64" 100 NIL NIL NIL)'
    b' "MIXED" NIL NIL NIL))'
)


def structure_of(raw: bytes, uid: int):
    parsed = parse_fetch_response([raw])
    assert uid in parsed
    return parsed[uid]


def test_zip_report_detected():
    assert has_report_attachment(structure_of(ZIP_REPORT, 4711)) is True


def test_plain_text_not_a_report():
    assert has_report_attachment(structure_of(PLAIN_TEXT, 4712)) is False


def test_html_newsletter_not_a_report():
    assert has_report_attachment(structure_of(HTML_NEWSLETTER, 4713)) is False


def test_pdf_attachment_not_a_report():
    assert has_report_attachment(structure_of(PDF_INVOICE, 4714)) is False


def test_octet_stream_with_gz_filename_detected():
    assert has_report_attachment(structure_of(OCTET_STREAM_GZ, 4715)) is True


def test_nested_multipart_detected():
    assert has_report_attachment(structure_of(NESTED_GZIP, 4716)) is True


def test_batched_response_parses_all_messages():
    parsed = parse_fetch_response([ZIP_REPORT, PLAIN_TEXT, PDF_INVOICE])
    assert set(parsed) == {4711, 4712, 4714}


def test_literal_filename_reassembled():
    # imaplib represents string literals as (prefix-with-{n}, literal) tuples
    data = [
        (
            b'7 (UID 4717 BODYSTRUCTURE (("TEXT" "PLAIN" NIL NIL NIL "7BIT" 2 1)'
            b'("APPLICATION" "OCTET-STREAM" ("NAME" {32}',
            b"outlook.com!example.com!1!2.zip",
        ),
        b') NIL NIL "BASE64" 999 NIL NIL NIL) "MIXED" NIL NIL NIL))',
    ]
    parsed = parse_fetch_response(data)
    assert 4717 in parsed
    assert has_report_attachment(parsed[4717]) is True


def test_garbage_fails_open():
    # unparseable responses yield no entries -> callers download (fail open)
    assert parse_fetch_response([b"7 (UID 9 BODYSTRUCTURE (((("]) == {}
    assert parse_fetch_response([]) == {}
    assert parse_fetch_response(None) == {}


def test_missing_uid_or_structure_omitted():
    assert parse_fetch_response([b'8 (FLAGS (\\Seen))']) == {}
