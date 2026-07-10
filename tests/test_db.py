from conftest import DAY, T0, make_record, make_report


def test_import_and_domains(db):
    assert db.import_report(make_report()) is True
    assert db.import_report(make_report(domain="other.org", report_id="r-002")) is True
    domains = db.domains()
    assert [d["domain"] for d in domains] == ["example.com", "other.org"]
    assert domains[0]["report_count"] == 1
    assert domains[0]["message_count"] == 5


def test_duplicate_report_skipped(db):
    assert db.import_report(make_report()) is True
    assert db.import_report(make_report()) is False  # same (org_name, report_id)
    assert db.domains()[0]["report_count"] == 1
    # same report_id from a different org is a different report
    assert db.import_report(make_report(org_name="yahoo.com")) is True


def test_summary_weighted_counts(db):
    db.import_report(
        make_report(
            records=[
                make_record(count=8, eval_dkim="pass", eval_spf="fail"),
                make_record(
                    source_ip="198.51.100.7",
                    count=2,
                    eval_dkim="fail",
                    eval_spf="fail",
                    disposition="reject",
                ),
            ]
        )
    )
    s = db.summary("example.com", T0 - DAY, T0 + DAY)
    assert s["total_messages"] == 10
    assert s["dmarc_pass"] == 8
    assert s["dmarc_fail"] == 2
    assert s["dkim_pass"] == 8
    assert s["spf_pass"] == 0
    assert s["dispositions"] == {"none": 8, "quarantine": 0, "reject": 2}
    assert s["distinct_sources"] == 2


def test_summary_respects_domain_and_range(db):
    db.import_report(make_report())
    db.import_report(make_report(domain="other.org", report_id="r-002"))
    assert db.summary("example.com", T0 - DAY, T0 + DAY)["total_messages"] == 5
    assert db.summary("example.com", T0 + DAY, T0 + 2 * DAY)["total_messages"] == 0
    assert db.summary("nosuch.tld", T0 - DAY, T0 + DAY)["total_messages"] == 0


def test_timeseries_buckets(db):
    db.import_report(make_report(report_id="a", date_begin=T0))
    db.import_report(
        make_report(
            report_id="b",
            date_begin=T0 + 2 * DAY,
            records=[make_record(count=3, eval_dkim="fail", eval_spf="fail")],
        )
    )
    ts = db.timeseries("example.com", T0, T0 + 3 * DAY, "day")
    assert ts == [
        {"bucket": T0, "pass": 5, "fail": 0, "quarantine": 0, "reject": 0},
        {"bucket": T0 + 2 * DAY, "pass": 0, "fail": 3, "quarantine": 0, "reject": 0},
    ]


def test_timeseries_rejects_bad_interval(db):
    import pytest

    with pytest.raises(ValueError, match="invalid interval"):
        db.timeseries("example.com", 0, 1, "hour; DROP TABLE reports")


def test_alignment_combos(db):
    db.import_report(
        make_report(
            records=[
                make_record(count=4, eval_dkim="pass", eval_spf="pass"),
                make_record(count=3, eval_dkim="pass", eval_spf="fail"),
                make_record(count=1, eval_dkim="fail", eval_spf="fail"),
            ]
        )
    )
    combos = {(a["dkim"], a["spf"]): a["count"] for a in db.alignment("example.com", 0, T0 + DAY)}
    assert combos == {("pass", "pass"): 4, ("pass", "fail"): 3, ("fail", "fail"): 1}


def test_sources_aggregation_and_paging(db):
    db.import_report(
        make_report(
            records=[
                make_record(source_ip="192.0.2.10", count=5),
                make_record(source_ip="192.0.2.10", count=2, eval_dkim="fail", eval_spf="fail"),
                make_record(source_ip="198.51.100.7", count=1),
            ]
        )
    )
    result = db.sources("example.com", 0, T0 + DAY)
    assert result["total_rows"] == 2
    top = result["sources"][0]
    assert top["source_ip"] == "192.0.2.10"
    assert top["total"] == 7
    assert top["pass"] == 5
    assert top["fail"] == 2
    paged = db.sources("example.com", 0, T0 + DAY, limit=1, offset=1)
    assert paged["total_rows"] == 2
    assert [s["source_ip"] for s in paged["sources"]] == ["198.51.100.7"]


def test_reports_list_and_detail(db):
    db.import_report(
        make_report(
            records=[
                make_record(count=5),
                make_record(source_ip="198.51.100.7", count=2, eval_dkim="fail", eval_spf="fail"),
            ]
        )
    )
    listing = db.reports("example.com", 0, T0 + DAY)
    assert listing["total"] == 1
    entry = listing["reports"][0]
    assert entry["message_count"] == 7
    assert entry["fail_count"] == 2

    detail = db.report_detail(entry["id"])
    assert detail["org_name"] == "google.com"
    assert detail["policy_p"] == "quarantine"
    assert len(detail["records"]) == 2
    assert detail["records"][0]["auth_results"][0]["auth_type"] == "dkim"
    assert db.report_detail(99_999) is None


def test_processed_messages(db):
    assert db.is_message_processed(1, 42) is False
    db.mark_message_processed(1, 42, "<m1@x>", "imported")
    assert db.is_message_processed(1, 42) is True
    # upsert on re-processing (e.g. after UIDVALIDITY-preserving retry)
    db.mark_message_processed(1, 42, "<m1@x>", "parse_error", "boom")
    assert db.is_message_processed(1, 42) is True


def test_meta_roundtrip(db):
    assert db.get_meta("schema_version") == "1"
    assert db.get_meta("nope") is None
    db.set_meta("last_sync_at", "123")
    db.set_meta("last_sync_at", "456")
    assert db.get_meta("last_sync_at") == "456"
