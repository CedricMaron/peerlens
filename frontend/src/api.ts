import type {
  AnalyzeResponse,
  Branch,
  ChallengeResult,
  CompileGate,
  Issue,
  LiteratureAnalysis,
  LiteratureItem,
  LiteratureSearchResult,
  Manuscript,
  PaperSummary,
  ProviderSettings,
  Readiness,
  ResearchInputListItem,
  ResearchItem,
  SectionDetail,
  UsageOverview,
  UsageSummary,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === 'string'
        ? detail
        : detail && typeof detail === 'object' && 'message' in (detail as object)
          ? String((detail as { message: unknown }).message)
          : `Request failed with status ${status}`
    super(message)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers:
      init?.body instanceof FormData
        ? init?.headers
        : { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let detail: unknown = await response.text()
    try {
      detail = JSON.parse(detail as string)
      if (detail && typeof detail === 'object' && 'detail' in (detail as object)) {
        detail = (detail as { detail: unknown }).detail
      }
    } catch {
      /* plain-text error body */
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

const get = <T,>(path: string) => request<T>(path)
const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
const patch = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })
const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
const del = <T,>(path: string) => request<T>(path, { method: 'DELETE' })

export const api = {
  // Branches & papers
  listBranches: () => get<Branch[]>('/branches'),
  createBranch: (name: string, description: string) =>
    post<Branch>('/branches', { name, description }),
  getBranch: (id: number) => get<Branch>(`/branches/${id}`),
  updateBranch: (id: number, body: { name?: string; description?: string }) =>
    patch<Branch>(`/branches/${id}`, body),
  deleteBranch: (id: number) => del<void>(`/branches/${id}`),

  createPaper: (branchId: number, title: string, notes = '') =>
    post<PaperSummary>(`/branches/${branchId}/papers`, { title, notes }),
  getPaper: (id: number) => get<PaperSummary>(`/papers/${id}`),
  updatePaper: (id: number, body: { title?: string; notes?: string }) =>
    patch<PaperSummary>(`/papers/${id}`, body),
  deletePaper: (id: number) => del<void>(`/papers/${id}`),

  // Research inputs
  listInputs: (paperId: number) => get<ResearchInputListItem[]>(`/papers/${paperId}/inputs`),
  addTextInput: (paperId: number, label: string, content: string) =>
    post<{ id: number }>(`/papers/${paperId}/inputs`, { label, content }),
  uploadInputs: (paperId: number, files: File[], label = '') => {
    const form = new FormData()
    files.forEach((file) => form.append('files', file))
    form.append('label', label)
    return request<{ id: number }[]>(`/papers/${paperId}/inputs/upload`, {
      method: 'POST',
      body: form,
    })
  },
  deleteInput: (inputId: number) => del<void>(`/inputs/${inputId}`),

  // Checklist
  getReadiness: (paperId: number) => get<Readiness>(`/papers/${paperId}/readiness`),
  getSection: (paperId: number, key: string) =>
    get<SectionDetail>(`/papers/${paperId}/sections/${key}`),
  analyze: (paperId: number, sections?: string[]) =>
    post<AnalyzeResponse>(`/papers/${paperId}/analyze`, { sections, run_review: true }),
  reviewSection: (paperId: number, key: string) =>
    post<SectionDetail>(`/papers/${paperId}/sections/${key}/review`),
  recheckSection: (paperId: number, key: string) =>
    post<SectionDetail>(`/papers/${paperId}/sections/${key}/recheck`),
  challenge: (paperId: number) => post<ChallengeResult>(`/papers/${paperId}/challenge`),
  listIssues: (paperId: number, status = 'open') =>
    get<Issue[]>(`/papers/${paperId}/issues?status=${status}`),
  updateIssue: (issueId: number, status: 'open' | 'resolved' | 'dismissed') =>
    patch<Issue>(`/issues/${issueId}`, { status }),

  // Human control over understanding
  createItem: (
    paperId: number,
    body: { section_key: string; label?: string; statement: string; details?: Record<string, string> },
  ) => post<ResearchItem>(`/papers/${paperId}/items`, body),
  editItem: (itemId: number, body: { statement?: string; details?: Record<string, string>; label?: string }) =>
    patch<ResearchItem>(`/items/${itemId}`, body),
  confirmItem: (itemId: number) => post<ResearchItem>(`/items/${itemId}/confirm`),
  rejectItem: (itemId: number) => post<ResearchItem>(`/items/${itemId}/reject`),

  // Literature
  searchLiterature: (q: string, branchId?: number) =>
    get<LiteratureSearchResult[]>(
      `/literature/search?q=${encodeURIComponent(q)}${branchId ? `&branch_id=${branchId}` : ''}`,
    ),
  lookupDoi: (doi: string) =>
    get<LiteratureSearchResult>(`/literature/doi?doi=${encodeURIComponent(doi)}`),
  listLiterature: (branchId: number) => get<LiteratureItem[]>(`/branches/${branchId}/literature`),
  listPaperLiterature: (paperId: number) => get<LiteratureItem[]>(`/papers/${paperId}/literature`),
  addLiterature: (branchId: number, body: Record<string, unknown>) =>
    post<LiteratureItem>(`/branches/${branchId}/literature`, body),
  updateLiterature: (id: number, body: Record<string, unknown>) =>
    patch<LiteratureItem>(`/literature/${id}`, body),
  deleteLiterature: (id: number) => del<void>(`/literature/${id}`),
  attachLiterature: (paperId: number, literatureId: number) =>
    post<void>(`/papers/${paperId}/literature/${literatureId}`),
  detachLiterature: (paperId: number, literatureId: number) =>
    del<void>(`/papers/${paperId}/literature/${literatureId}`),
  analyzeLiterature: (paperId: number) =>
    post<LiteratureAnalysis>(`/papers/${paperId}/literature/analyze`),

  // Manuscript
  getGate: (paperId: number) => get<CompileGate>(`/papers/${paperId}/manuscript/gate`),
  compileManuscript: (paperId: number) => post<Manuscript>(`/papers/${paperId}/manuscript`),
  listManuscripts: (paperId: number) => get<Manuscript[]>(`/papers/${paperId}/manuscripts`),
  manuscriptDownloadUrl: (id: number) => `${BASE}/manuscripts/${id}/markdown`,

  // Settings
  getProvider: () => get<ProviderSettings>('/settings/provider'),
  saveProvider: (body: { provider: string; model: string; api_key?: string; base_url?: string }) =>
    put<ProviderSettings>('/settings/provider', body),
  clearApiKey: () => del<ProviderSettings>('/settings/provider/key'),
  testProvider: (body: {
    provider?: string
    model?: string
    api_key?: string
    base_url?: string
  }) => post<{ ok: boolean; message: string }>('/settings/provider/test', body),
  ollamaModels: (baseUrl?: string) =>
    get<string[]>(`/settings/ollama/models${baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : ''}`),

  // Usage
  getUsage: (params: { paper_id?: number; branch_id?: number; since_days?: number } = {}) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) query.set(key, String(value))
    })
    const suffix = query.toString()
    return get<UsageOverview>(`/usage${suffix ? `?${suffix}` : ''}`)
  },
  getUsageSummary: () => get<UsageSummary>('/usage/summary'),
}
