import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Banner, Empty, Modal, Spinner, errorMessage } from './common'
import type { LiteratureItem, LiteratureSearchResult } from '../types'

function authorLine(authors: string[]): string {
  if (authors.length === 0) return 'unknown authors'
  if (authors.length <= 3) return authors.join(', ')
  return `${authors.slice(0, 3).join(', ')} et al.`
}

export default function LiteraturePanel({
  branchId,
  paperId,
  onChange,
}: {
  branchId: number
  paperId?: number
  onChange?: () => void
}) {
  const [items, setItems] = useState<LiteratureItem[]>([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<LiteratureSearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState('')
  const [manual, setManual] = useState(false)

  const load = useCallback(() => {
    api
      .listLiterature(branchId)
      .then(setItems)
      .catch((e) => setError(errorMessage(e)))
  }, [branchId])

  useEffect(load, [load])

  const search = async () => {
    if (query.trim().length < 2) return
    setSearching(true)
    setError('')
    try {
      const trimmed = query.trim()
      // A DOI is a precise lookup; anything else is a keyword search.
      if (/^(https?:\/\/doi\.org\/|doi:)?10\.\d{4,}\//i.test(trimmed)) {
        setResults([await api.lookupDoi(trimmed)])
      } else {
        setResults(await api.searchLiterature(trimmed, branchId))
      }
    } catch (e) {
      setError(errorMessage(e))
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  const add = async (result: LiteratureSearchResult) => {
    try {
      await api.addLiterature(branchId, { ...result, paper_id: paperId })
      load()
      onChange?.()
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div>
      <div className="card">
        <div className="card-title">Search literature</div>
        <div className="row" style={{ flexWrap: 'nowrap' }}>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && search()}
            placeholder="Title, keywords, or a DOI (10.xxxx/…)"
          />
          <button className="primary" onClick={search} disabled={searching || query.trim().length < 2}>
            {searching ? <Spinner /> : 'Search'}
          </button>
          <button onClick={() => setManual(true)}>Add manually</button>
        </div>
        <p className="dim" style={{ margin: '0.5rem 0 0' }}>
          Searches OpenAlex. PeerLens never invents references, and never concludes that no
          prior work exists because a search returned nothing.
        </p>
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      {results && (
        <div className="card" style={{ marginTop: '0.85rem' }}>
          <div className="card-title">
            {results.length} result{results.length === 1 ? '' : 's'} from OpenAlex
          </div>
          {results.length === 0 && (
            <p className="dim">
              No equivalent work was identified in this search. That is not evidence that none
              exists — try different terms or venues.
            </p>
          )}
          <div className="stack" style={{ gap: '0.6rem' }}>
            {results.map((result, index) => (
              <div key={result.external_id ?? index} style={{ borderTop: index ? '1px solid var(--border)' : 'none', paddingTop: index ? '0.6rem' : 0 }}>
                <div className="row">
                  <strong>{result.title}</strong>
                  {result.already_in_library && <span className="pill ready">in library</span>}
                </div>
                <div className="dim">
                  {authorLine(result.authors)} · {result.year ?? 'year unknown'}
                  {result.venue ? ` · ${result.venue}` : ''}
                  {result.cited_by_count !== null ? ` · ${result.cited_by_count} citations` : ''}
                </div>
                {result.abstract && (
                  <p className="dim" style={{ margin: '0.3rem 0' }}>
                    {result.abstract.slice(0, 320)}
                    {result.abstract.length > 320 ? '…' : ''}
                  </p>
                )}
                <div className="row">
                  <button className="small" onClick={() => add(result)} disabled={result.already_in_library}>
                    Add to library
                  </button>
                  {result.url && (
                    <a href={result.url} target="_blank" rel="noreferrer" className="dim">
                      Open source ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <h3 style={{ margin: '1.4rem 0 0.6rem' }}>Library ({items.length})</h3>
      {items.length === 0 ? (
        <Empty>No references yet. Search above, or add one manually.</Empty>
      ) : (
        <div className="stack" style={{ gap: '0.5rem' }}>
          {items.map((item) => (
            <div className="card" key={item.id} style={{ padding: '0.7rem 0.9rem' }}>
              <div className="row">
                <span className="mono dim">L{item.id}</span>
                <strong>{item.title}</strong>
                <span className={`pill ${item.verification_status === 'verified' ? 'ready' : 'incomplete'}`}>
                  {item.verification_status}
                </span>
                <span style={{ marginLeft: 'auto' }}>
                  <button
                    className="small subtle danger"
                    onClick={async () => {
                      if (!confirm(`Remove "${item.title}" from the library?`)) return
                      await api.deleteLiterature(item.id)
                      load()
                      onChange?.()
                    }}
                  >
                    Remove
                  </button>
                </span>
              </div>
              <div className="dim">
                {authorLine(item.authors)} · {item.year ?? 'year unknown'}
                {item.venue ? ` · ${item.venue}` : ''}
                {item.doi ? ` · DOI ${item.doi}` : ''} · source: {item.source}
              </div>
              {paperId !== undefined && (
                <div className="row" style={{ marginTop: '0.4rem' }}>
                  {item.attached_paper_ids.includes(paperId) ? (
                    <button
                      className="small"
                      onClick={async () => {
                        await api.detachLiterature(paperId, item.id)
                        load()
                      }}
                    >
                      Detach from this paper
                    </button>
                  ) : (
                    <button
                      className="small"
                      onClick={async () => {
                        await api.attachLiterature(paperId, item.id)
                        load()
                      }}
                    >
                      Attach to this paper
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {manual && (
        <ManualEntry
          branchId={branchId}
          paperId={paperId}
          onClose={() => setManual(false)}
          onSaved={() => {
            setManual(false)
            load()
            onChange?.()
          }}
        />
      )}
    </div>
  )
}

function ManualEntry({
  branchId,
  paperId,
  onClose,
  onSaved,
}: {
  branchId: number
  paperId?: number
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState({
    title: '',
    authors: '',
    year: '',
    doi: '',
    venue: '',
    abstract: '',
    url: '',
    relation_to_research: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (key: keyof typeof form, value: string) =>
    setForm((current) => ({ ...current, [key]: value }))

  const save = async () => {
    if (!form.title.trim()) return
    setSaving(true)
    try {
      await api.addLiterature(branchId, {
        title: form.title.trim(),
        authors: form.authors
          .split(',')
          .map((a) => a.trim())
          .filter(Boolean),
        year: form.year ? Number(form.year) : null,
        doi: form.doi.trim() || null,
        venue: form.venue.trim(),
        abstract: form.abstract,
        url: form.url.trim() || null,
        relation_to_research: form.relation_to_research,
        source: 'manual',
        // Manually entered references are unverified until checked against a source.
        verification_status: 'unverified',
        paper_id: paperId,
      })
      onSaved()
    } catch (e) {
      setError(errorMessage(e))
      setSaving(false)
    }
  }

  return (
    <Modal title="Add reference manually" onClose={onClose}>
      {error && <Banner kind="error">{error}</Banner>}
      <div className="field">
        <label>Title</label>
        <input value={form.title} autoFocus onChange={(e) => set('title', e.target.value)} />
      </div>
      <div className="grid-2">
        <div className="field">
          <label>Authors (comma-separated)</label>
          <input value={form.authors} onChange={(e) => set('authors', e.target.value)} />
        </div>
        <div className="field">
          <label>Year</label>
          <input value={form.year} onChange={(e) => set('year', e.target.value)} inputMode="numeric" />
        </div>
        <div className="field">
          <label>DOI</label>
          <input value={form.doi} onChange={(e) => set('doi', e.target.value)} />
        </div>
        <div className="field">
          <label>Venue</label>
          <input value={form.venue} onChange={(e) => set('venue', e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label>Abstract or key content</label>
        <textarea value={form.abstract} onChange={(e) => set('abstract', e.target.value)} />
      </div>
      <div className="field">
        <label>Relation to your research</label>
        <input
          value={form.relation_to_research}
          onChange={(e) => set('relation_to_research', e.target.value)}
          placeholder="e.g. closest prior work — uses a single global teacher"
        />
      </div>
      <p className="dim">
        Manually entered references are marked <strong>unverified</strong> until you confirm
        them against the actual source.
      </p>
      <div className="modal-actions">
        <button onClick={onClose}>Cancel</button>
        <button className="primary" onClick={save} disabled={saving || !form.title.trim()}>
          {saving ? <Spinner /> : 'Add reference'}
        </button>
      </div>
    </Modal>
  )
}
