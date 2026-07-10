from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import DAY, T0, make_record, make_report
from dmarcayn.config import (
    Config,
    ImapConfig,
    LimitsConfig,
    ServerConfig,
    StorageConfig,
    SyncConfig,
)
from dmarcayn.server import create_app


@pytest.fixture
def client(db, tmp_path):
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>dmarcayn</title>")
    config = Config(
        imap=ImapConfig(
            host="h", port=993, username="u", password="p",
            mailbox="INBOX", delete_after_import=False,
        ),
        sync=SyncConfig(poll_interval_minutes=30),
        server=ServerConfig(host="127.0.0.1", port=8080, static_dir=static_dir),
        storage=StorageConfig(database_path=Path("unused")),
        limits=LimitsConfig(max_attachment_bytes=1, max_decompressed_bytes=1),
    )
    db.import_report(
        make_report(
            records=[
                make_record(count=8),
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
    db.import_report(make_report(domain="other.org", report_id="r-002"))
    app = create_app(config, db, poller=None)
    with TestClient(app) as test_client:
        yield test_client


RANGE = {"from": T0 - DAY, "to": T0 + DAY}


def test_domains(client):
    body = client.get("/api/domains").json()
    assert [d["domain"] for d in body] == ["example.com", "other.org"]
    assert body[0]["message_count"] == 10


def test_summary(client):
    body = client.get("/api/summary", params={"domain": "example.com", **RANGE}).json()
    assert body["total_messages"] == 10
    assert body["dmarc_pass"] == 8
    assert body["dmarc_fail"] == 2
    assert body["dispositions"]["reject"] == 2


def test_summary_requires_params(client):
    assert client.get("/api/summary").status_code == 422
    bad_from = client.get("/api/summary", params={"domain": "x", "from": "abc", "to": 1})
    assert bad_from.status_code == 422


def test_timeseries(client):
    body = client.get(
        "/api/timeseries", params={"domain": "example.com", "interval": "day", **RANGE}
    ).json()
    assert body == [{"bucket": T0, "pass": 8, "fail": 2, "quarantine": 0, "reject": 2}]


def test_timeseries_rejects_bad_interval(client):
    response = client.get(
        "/api/timeseries", params={"domain": "example.com", "interval": "century", **RANGE}
    )
    assert response.status_code == 400


def test_alignment(client):
    body = client.get("/api/alignment", params={"domain": "example.com", **RANGE}).json()
    assert {(a["dkim"], a["spf"]): a["count"] for a in body} == {
        ("pass", "pass"): 8,
        ("fail", "fail"): 2,
    }


def test_sources_paging_and_limits(client):
    body = client.get(
        "/api/sources", params={"domain": "example.com", "limit": 1, **RANGE}
    ).json()
    assert body["total_rows"] == 2
    assert body["sources"][0]["source_ip"] == "192.0.2.10"
    assert client.get(
        "/api/sources", params={"domain": "example.com", "limit": 100000, **RANGE}
    ).status_code == 422


def test_reports_and_detail(client):
    listing = client.get("/api/reports", params={"domain": "example.com", **RANGE}).json()
    assert listing["total"] == 1
    report_id = listing["reports"][0]["id"]

    detail = client.get(f"/api/reports/{report_id}").json()
    assert detail["org_name"] == "google.com"
    assert len(detail["records"]) == 2
    assert detail["records"][0]["auth_results"]

    assert client.get("/api/reports/99999").status_code == 404
    assert client.get("/api/reports/not-a-number").status_code == 422


def test_sync_without_poller(client):
    assert client.post("/api/sync").status_code == 503
    body = client.get("/api/sync/status").json()
    assert body["running"] is False


def test_static_frontend_and_headers(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "dmarcayn" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"


def test_no_openapi_exposure(client):
    assert client.get("/api/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
