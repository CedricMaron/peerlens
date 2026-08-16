import { useCallback, useEffect, useState } from 'react'
import { notifyUsageChanged } from '../App'
import { api } from '../api'
import IssueCard from './IssueCard'
import {
  Banner,
  ProvenanceTag,
  Spinner,
  StatusPill,
  errorMessage,
  formatDate,
} from './common'
import type { ResearchItem, SectionDetail } from '../types'

/** Editable view of one extracted item — the researcher's correction surface. */
function ItemCard({
  item,
  onChanged,
}: {
  item: ResearchItem
  onChanged: () => void | Promise<void>
}) {
  const [editing, setEditing] = useState(false)
  const [statement, setStatement] = useState(item.statement)
  const [details, setDetails] = useState(JSON.stringify(item.details, null, 2))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      let parsed: Record<string, string> | undefined
      try {
        parsed = JSON.parse(details)
      } catch {
        setError('Details must be valid JSON (an object of string values).')
        setBusy(false)
        return
      }
      await api.editItem(item.id, { statement, details: parsed })
      setEditing(false)
      await onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const act = async (action: 'confirm' | 'reject') => {
    setBusy(true)
    try {
      if (action === 'confirm') await api.confirmItem(item.id)
      else await api.rejectItem(item.id)
      await onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="item">
      <div className="item-head">
        <span className="item-label">{item.label}</span>
        <ProvenanceTag provenance={item.provenance} />
        {item.confirmation === 'confirmed' && <span className="prov confirmed">confirmed</span>}
        {item.confirmation === 'edited' && <span className="prov edited">edited by you</span>}
        <span className="dim" style={{ marginLeft: 'auto' }}>
          {item.source_input_ids.length > 0
            ? `Sources: ${item.source_input_ids.map((s) => `#${s}`).join(', ')}`
            : 'No direct source'}
        </span>
      </div>

      {editing ? (
        <>
          <div className="field">
            <label>Statement</label>
            <textarea value={statement} onChange={(e) => setStatement(e.target.value)} />
          </div>
          <div className="field">
            <label>Details (JSON)</label>
            <textarea
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              style={{ fontFamily: 'var(--mono)', fontSize: '0.85rem' }}
            />
          </div>
          {error && <Banner kind="error">{error}</Banner>}
          <div className="item-actions">
            <button className="primary small" onClick={save} disabled={busy}>
              {busy ? <Spinner /> : 'Save correction'}
            </button>
            <button className="small" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="item-statement">{item.statement}</div>
          {Object.keys(item.details ?? {}).length > 0 && (
            <dl className="item-details">
              {Object.entries(item.details).map(([key, value]) => (
                <div key={key} style={{ display: 'contents' }}>
                  <dt>{key}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          )}
          {error && <Banner kind="error">{error}</Banner>}
          <div className="item-actions">
            {item.confirmation !== 'confirmed' && (
              <button className="small" onClick={() => act('confirm')} disabled={busy}>
                Confirm
              </button>
            )}
            <button className="small" onClick={() => setEditing(true)} disabled={busy}>
              Edit
            </button>
            <button className="small subtle danger" onClick={() => act('reject')} disabled={busy}>
              Reject
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export default function SectionDrawer({
  paperId,
  sectionKey,
  onClose,
  onChanged,
  onAddResearch,
}: {
  paperId: number
  sectionKey: string
  onClose: () => void
  onChanged: () => void | Promise<void>
  onAddResearch: () => void
}) {
  const [detail, setDetail] = useState<SectionDetail | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  const load = useCallback(async () => {
    try {
      setDetail(await api.getSection(paperId, sectionKey))
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [paperId, sectionKey])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const run = async (mode: 'review' | 'recheck') => {
    setBusy(mode === 'review' ? 'Re-checking this section…' : 'Re-extracting and re-checking…')
    setError('')
    try {
      const updated =
        mode === 'review'
          ? await api.reviewSection(paperId, sectionKey)
          : await api.recheckSection(paperId, sectionKey)
      setDetail(updated)
      await onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy('')
      notifyUsageChanged()
    }
  }

  const afterItemChange = async () => {
    await load()
    await onChanged()
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer">
        {!detail ? (
          <div className="empty">
            <Spinner /> Loading…
          </div>
        ) : (
          <>
            <div className="drawer-head">
              <div style={{ flex: 1 }}>
                <div className="dim">Checklist section {detail.number}</div>
                <h2>{detail.title}</h2>
                <div className="row" style={{ marginTop: '0.35rem' }}>
                  <StatusPill status={detail.status} />
                  {detail.needs_recheck && <span className="pill stale">re-check needed</span>}
                </div>
              </div>
              <button className="subtle" onClick={onClose} aria-label="Close">
                ✕
              </button>
            </div>

            <p className="dim">{detail.purpose}</p>

            {detail.needs_recheck && detail.recheck_reason && (
              <Banner kind="warn">{detail.recheck_reason}</Banner>
            )}
            {error && <Banner kind="error">{error}</Banner>}
            {busy && (
              <Banner kind="info">
                <Spinner /> {busy}
              </Banner>
            )}

            <div className="row" style={{ margin: '0.9rem 0 1.2rem' }}>
              <button className="primary" onClick={onAddResearch} disabled={!!busy}>
                Add Information
              </button>
              <button onClick={() => run('recheck')} disabled={!!busy}>
                Re-check
              </button>
              <button onClick={() => run('review')} disabled={!!busy}>
                Review only
              </button>
            </div>

            <div className="section-block">
              <h3>What PeerLens understands</h3>
              {detail.summary ? (
                <p className="muted">{detail.summary}</p>
              ) : (
                <p className="dim">
                  Nothing extracted yet for this section. Add relevant research material,
                  then run Analyze.
                </p>
              )}
              {detail.items.length > 0 && (
                <div className="stack" style={{ gap: '0.5rem', marginTop: '0.6rem' }}>
                  {detail.items.map((item) => (
                    <ItemCard key={item.id} item={item} onChanged={afterItemChange} />
                  ))}
                </div>
              )}
            </div>

            {detail.relationships.length > 0 && (
              <div className="section-block">
                <h3>Scientific relationships</h3>
                <div className="stack" style={{ gap: '0.2rem' }}>
                  {detail.relationships.map((relation) => (
                    <div key={relation.id} className="mono dim">
                      {relation.source_label} —{relation.rel_type}→ {relation.target_label}
                      {relation.rationale ? ` · ${relation.rationale}` : ''}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detail.checks.length > 0 && (
              <div className="section-block">
                <h3>Checks</h3>
                {detail.checks.map((check, index) => (
                  <div className={`check ${check.status}`} key={index}>
                    <span className="mark">
                      {check.status === 'pass' ? '✓' : check.status === 'fail' ? '✗' : '?'}
                    </span>
                    <span>
                      <strong>{check.criterion}</strong>
                      {check.reason && <div className="reason">{check.reason}</div>}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {detail.issues.length > 0 && (
              <div className="section-block">
                <h3>Issues</h3>
                <div className="stack" style={{ gap: '0.5rem' }}>
                  {detail.issues.map((issue) => (
                    <IssueCard key={issue.id} issue={issue} onChanged={afterItemChange} />
                  ))}
                </div>
              </div>
            )}

            {detail.missing_information.length > 0 && (
              <div className="section-block">
                <h3>Missing information</h3>
                <div className="stack" style={{ gap: '0.4rem' }}>
                  {detail.missing_information.map((missing, index) => (
                    <div className="card" key={index} style={{ padding: '0.6rem 0.8rem' }}>
                      <strong>{missing.item}</strong>
                      {missing.why_needed && <div className="dim">{missing.why_needed}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {detail.sources.length > 0 && (
              <div className="section-block">
                <h3>Sources this understanding came from</h3>
                <div className="stack" style={{ gap: '0.3rem' }}>
                  {detail.sources.map((source) => (
                    <div key={source.id} className="dim">
                      <span className="mono">#{source.id}</span> {source.label}
                      {source.original_filename ? ` (${source.original_filename})` : ''}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="dim" style={{ marginTop: '1.5rem' }}>
              Extracted {formatDate(detail.last_extracted_at)} · Reviewed{' '}
              {formatDate(detail.last_reviewed_at)}
              {detail.depends_on.length > 0 && <> · Depends on: {detail.depends_on.join(', ')}</>}
            </div>
          </>
        )}
      </aside>
    </>
  )
}
