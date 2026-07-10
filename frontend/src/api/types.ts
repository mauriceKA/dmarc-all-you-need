/** TypeScript mirrors of the backend API response shapes (see backend/dmarcayn/server.py). */

export interface DomainInfo {
  domain: string
  report_count: number
  message_count: number
  first_seen: number
  last_seen: number
}

export interface Summary {
  total_messages: number
  dmarc_pass: number
  dmarc_fail: number
  dkim_pass: number
  spf_pass: number
  dispositions: { none: number; quarantine: number; reject: number }
  distinct_sources: number
  report_count: number
}

export interface TimeseriesBucket {
  bucket: number
  pass: number
  fail: number
  quarantine: number
  reject: number
}

export interface AlignmentCombo {
  dkim: 'pass' | 'fail'
  spf: 'pass' | 'fail'
  count: number
}

export interface SourceRow {
  source_ip: string
  total: number
  pass: number
  fail: number
  quarantine: number
  reject: number
  last_seen: number
}

export interface SourcesPage {
  total_rows: number
  sources: SourceRow[]
}

export interface ReportListEntry {
  id: number
  org_name: string
  report_id: string
  date_begin: number
  date_end: number
  message_count: number
  fail_count: number
}

export interface ReportsPage {
  total: number
  reports: ReportListEntry[]
}

export interface AuthResult {
  auth_type: 'dkim' | 'spf'
  domain: string | null
  selector: string | null
  scope: string | null
  result: string
}

export interface ReportRecord {
  id: number
  source_ip: string
  count: number
  disposition: string
  eval_dkim: string
  eval_spf: string
  dmarc_pass: number
  reason_type: string | null
  reason_comment: string | null
  header_from: string | null
  envelope_from: string | null
  envelope_to: string | null
  auth_results: AuthResult[]
}

export interface ReportDetail {
  id: number
  domain: string
  org_name: string
  org_email: string | null
  report_id: string
  date_begin: number
  date_end: number
  policy_adkim: string | null
  policy_aspf: string | null
  policy_p: string | null
  policy_sp: string | null
  policy_pct: number | null
  imported_at: number
  records: ReportRecord[]
}

export interface SyncResultInfo {
  fetched: number
  imported: number
  duplicates: number
  skipped: number
  errors: number
}

export interface SyncStatus {
  running: boolean
  last_run_at: number | null
  last_result: SyncResultInfo | null
  last_error: string | null
  next_run_at: number | null
}
