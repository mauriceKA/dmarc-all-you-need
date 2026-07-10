"""Dataclasses representing a parsed DMARC aggregate report (RFC 7489)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthResult:
    auth_type: str  # 'dkim' | 'spf'
    domain: str | None
    result: str
    selector: str | None = None  # dkim only
    scope: str | None = None  # spf only: 'helo' | 'mfrom'


@dataclass(frozen=True)
class ReportRecord:
    source_ip: str
    count: int
    disposition: str  # none | quarantine | reject
    eval_dkim: str  # pass | fail
    eval_spf: str  # pass | fail
    header_from: str | None
    envelope_from: str | None
    envelope_to: str | None
    reason_type: str | None
    reason_comment: str | None
    auth_results: tuple[AuthResult, ...] = field(default_factory=tuple)

    @property
    def dmarc_pass(self) -> bool:
        return self.eval_dkim == "pass" or self.eval_spf == "pass"


@dataclass(frozen=True)
class Report:
    domain: str  # policy_published/domain, lowercased
    org_name: str
    org_email: str | None
    report_id: str
    date_begin: int  # epoch seconds
    date_end: int
    policy_adkim: str | None
    policy_aspf: str | None
    policy_p: str | None
    policy_sp: str | None
    policy_pct: int | None
    records: tuple[ReportRecord, ...]
    raw_xml: bytes  # original XML, uncompressed
