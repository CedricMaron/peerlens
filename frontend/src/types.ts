export type SectionStatus = 'missing' | 'incomplete' | 'needs_attention' | 'ready'
export type Severity = 'blocker' | 'major' | 'minor' | 'note'
export type Provenance = 'provided' | 'extracted' | 'inferred' | 'suggested'
export type Confirmation = 'unconfirmed' | 'confirmed' | 'edited' | 'rejected'

export interface PaperSummary {
  id: number
  branch_id: number
  title: string
  notes: string
  created_at: string
  updated_at: string
}

export interface Branch {
  id: number
  name: string
  description: string
  created_at: string
  updated_at: string
  papers: PaperSummary[]
  literature_count: number
}

export interface ResearchInputListItem {
  id: number
  label: string
  kind: string
  original_filename: string | null
  byte_size: number
  extraction_note: string
  char_count: number
  created_at: string
  analyzed_at: string | null
  preview: string
}

export interface Issue {
  id: number
  section_key: string | null
  origin: string
  severity: Severity
  issue: string
  why_it_matters: string
  evidence: string
  recommended_action: string
  affected_sections: string[]
  status: string
  created_at: string
}

export interface ResearchItem {
  id: number
  section_key: string
  item_type: string
  label: string
  statement: string
  details: Record<string, string>
  provenance: Provenance
  confirmation: Confirmation
  source_input_ids: number[]
  order_index: number
  updated_at: string
}

export interface Relationship {
  id: number
  rel_type: string
  rationale: string
  source_label: string
  target_label: string
  source_section: string
  target_section: string
}

export interface SectionOverview {
  key: string
  number: number
  title: string
  purpose: string
  status: SectionStatus
  summary: string
  needs_recheck: boolean
  recheck_reason: string
  item_count: number
  issue_counts: Record<Severity, number>
  missing_count: number
  depends_on: string[]
  last_extracted_at: string | null
  last_reviewed_at: string | null
}

export interface CompileGate {
  can_compile: boolean
  reasons: string[]
  ready_sections: number
  required_sections: number
  open_blockers: number
}

export interface Readiness {
  sections: SectionOverview[]
  gate: CompileGate
  status_counts: Record<SectionStatus, number>
}

export interface Check {
  criterion: string
  status: 'pass' | 'fail' | 'unknown'
  reason: string
}

export interface MissingInformation {
  item: string
  why_needed: string
}

export interface SectionDetail {
  key: string
  number: number
  title: string
  purpose: string
  status: SectionStatus
  summary: string
  needs_recheck: boolean
  recheck_reason: string
  checks: Check[]
  missing_information: MissingInformation[]
  items: ResearchItem[]
  issues: Issue[]
  relationships: Relationship[]
  sources: ResearchInputListItem[]
  depends_on: string[]
  last_extracted_at: string | null
  last_reviewed_at: string | null
}

export interface ChallengeResult {
  overall_assessment: string
  cross_section_observations: string[]
  issues: Issue[]
  meta?: RunMeta | null
}

export interface AnalyzeResponse {
  extracted: Record<string, unknown>
  reviewed: string[]
  errors: Record<string, string>
  readiness: Readiness
  meta?: RunMeta | null
}

export interface LiteratureSearchResult {
  external_id: string | null
  title: string
  authors: string[]
  year: number | null
  doi: string | null
  abstract: string
  venue: string
  url: string | null
  cited_by_count: number | null
  source: string
  verification_status: string
  already_in_library: boolean
}

export interface LiteratureItem {
  id: number
  branch_id: number
  title: string
  authors: string[]
  year: number | null
  doi: string | null
  abstract: string
  url: string | null
  venue: string
  source: string
  verification_status: string
  relation_to_research: string
  relation_kind: string
  created_at: string
  attached_paper_ids: number[]
}

export interface LiteratureAnalysis {
  closest_prior_work: string[]
  existing_approaches: string[]
  important_baselines: string[]
  known_limitations: string[]
  contradictory_results: string[]
  relation_to_current_work: string
  search_caveat: string
}

export interface Manuscript {
  id: number
  paper_id: number
  title: string
  markdown: string
  sections: { sections?: { heading: string; markdown: string }[]; content_gaps?: string[] }
  created_at: string
}

export interface ProviderSettings {
  provider: string
  label: string
  kind: string
  is_local: boolean
  needs_api_key: boolean
  requires_model: boolean
  model: string
  base_url: string
  api_key_hint: string
  api_key_set: boolean
  from_environment: boolean
  configured: boolean
  defaults: { models: Record<string, string>; base_urls: Record<string, string> }
}

/** One row of Settings → AI Provider. */
export interface ProviderStatus {
  id: string
  label: string
  kind: 'cli' | 'api' | 'local' | string
  blurb: string
  setup_hint: string
  state:
    | 'ready'
    | 'not_installed'
    | 'not_authenticated'
    | 'not_configured'
    | 'unavailable'
    | 'unknown'
    | 'error'
  message: string
  installed: boolean | null
  authenticated: boolean | null
  configured: boolean
  available: boolean
  version: string
  model: string
  needs_api_key: boolean
  requires_model: boolean
  supports_login: boolean
  is_local: boolean
  is_subscription: boolean
  api_key_set: boolean
  api_key_hint: string
  base_url: string
  is_active: boolean
}

export interface ProviderStatusList {
  active_provider: string
  providers: ProviderStatus[]
}

export type LoginState =
  | 'IDLE'
  | 'LOGIN_STARTED'
  | 'LOGIN_SUCCESS'
  | 'LOGIN_FAILED'
  | 'LOGIN_CANCELLED'
  | 'LOGIN_ALREADY_RUNNING'
  | 'CLI_NOT_INSTALLED'

export interface LoginStatus {
  provider: string
  state: LoginState
  message: string
  url: string
  running: boolean
}

/** Provider metadata retained with a generated analysis, for reproducibility. */
export interface RunMeta {
  task_type: string
  operation?: string
  provider: string
  model: string | null
  created_at: string
  duration_ms: number | null
  usage: {
    input_tokens: number | null
    output_tokens: number | null
    cached_tokens: number | null
  }
}

export interface UsageTotals {
  calls: number
  input_tokens: number | null
  output_tokens: number | null
  cached_tokens: number | null
  total_tokens: number | null
  estimated_cost: number | null
  calls_with_unknown_cost: number
  failed_calls: number
  avg_latency_ms: number | null
}

export interface UsageRow {
  key: string
  calls: number
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  estimated_cost: number | null
}

export interface UsageEvent {
  id: number
  created_at: string
  paper_id: number | null
  operation: string
  provider: string
  model: string
  is_local: boolean
  input_tokens: number | null
  output_tokens: number | null
  cached_tokens: number | null
  latency_ms: number | null
  estimated_cost: number | null
  success: boolean
  error: string | null
}

export interface UsageOverview {
  totals: UsageTotals
  by_operation: UsageRow[]
  by_provider: UsageRow[]
  by_model: UsageRow[]
  by_paper: UsageRow[]
  by_branch: UsageRow[]
  by_location: UsageRow[]
  recent: UsageEvent[]
}

export interface UsageSummary {
  total_tokens: number | null
  estimated_cost: number | null
  calls: number
  cost_is_partial: boolean
}
