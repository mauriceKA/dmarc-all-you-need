import pytest

from dmarcayn.models import AuthResult, Report, ReportRecord

DAY = 86_400
T0 = 1_751_328_000  # 2025-07-01 00:00 UTC


def make_record(
    source_ip="192.0.2.10",
    count=5,
    disposition="none",
    eval_dkim="pass",
    eval_spf="pass",
    header_from="example.com",
    **kwargs,
):
    return ReportRecord(
        source_ip=source_ip,
        count=count,
        disposition=disposition,
        eval_dkim=eval_dkim,
        eval_spf=eval_spf,
        header_from=header_from,
        envelope_from=kwargs.get("envelope_from"),
        envelope_to=kwargs.get("envelope_to"),
        reason_type=kwargs.get("reason_type"),
        reason_comment=kwargs.get("reason_comment"),
        auth_results=kwargs.get(
            "auth_results",
            (
                AuthResult(auth_type="dkim", domain="example.com", selector="s1", result="pass"),
                AuthResult(auth_type="spf", domain="example.com", scope="mfrom", result="pass"),
            ),
        ),
    )


def make_report(
    domain="example.com",
    org_name="google.com",
    report_id="r-001",
    date_begin=T0,
    records=None,
    **kwargs,
):
    return Report(
        domain=domain,
        org_name=org_name,
        org_email=kwargs.get("org_email", "noreply@google.com"),
        report_id=report_id,
        date_begin=date_begin,
        date_end=kwargs.get("date_end", date_begin + DAY - 1),
        policy_adkim=kwargs.get("policy_adkim", "r"),
        policy_aspf=kwargs.get("policy_aspf", "r"),
        policy_p=kwargs.get("policy_p", "quarantine"),
        policy_sp=kwargs.get("policy_sp"),
        policy_pct=kwargs.get("policy_pct", 100),
        records=tuple(records) if records is not None else (make_record(),),
        raw_xml=kwargs.get("raw_xml", b"<feedback/>"),
    )


@pytest.fixture
def db(tmp_path):
    from dmarcayn.db import Database

    database = Database(tmp_path / "test.sqlite")
    yield database
    database.close()
