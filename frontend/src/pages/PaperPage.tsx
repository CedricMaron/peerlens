import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { notifyUsageChanged } from '../App'
import { api } from '../api'
import AddResearchModal from '../components/AddResearchModal'
import ChallengeModal from '../components/ChallengeModal'
import ManuscriptModal from '../components/ManuscriptModal'
import SectionDrawer from '../components/SectionDrawer'
import {
  Banner,
  Spinner,
  StatusIcon,
  errorMessage,
  formatDate,
} from '../components/common'
import type { PaperSummary, Readiness, ResearchInputListItem } from '../types'

export default function PaperPage() {
  const { paperId } = useParams()
  const id = Number(paperId)

  const [paper, setPaper] = useState<PaperSummary | null>(null)
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const [inputs, setInputs] = useState<ResearchInputListItem[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [openSection, setOpenSection] = useState<string | null>(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showChallenge, setShowChallenge] = useState(false)
  const [showManuscript, setShowManuscript] = useState(false)

  const load = useCallback(async () => {
    try {
      const [p, r, i] = await Promise.all([
        api.getPaper(id),
        api.getReadiness(id),
        api.listInputs(id),
      ])
      setPaper(p)
      setReadiness(r)
      setInputs(i)
    } catch (e) {
      setError(errorMessage(e))
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  const analyze = async () => {
    setBusy('Analyzing research…')
    setError('')
    try {
      const result = await api.analyze(id)
      setReadiness(result.readiness)
      const failures = Object.entries(result.errors)
      if (failures.length > 0) {
        setError(
          `Analysis completed with ${failures.length} section error(s): ` +
            failures.map(([key, message]) => `${key}: ${message}`).join(' | '),
        )
      }
      await load()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy('')
      notifyUsageChanged()
    }
  }

  if (error && !paper) return <main className="page"><Banner kind="error">{error}</Banner></main>
  if (!paper || !readiness)
    return (
      <main className="page">
        <div className="empty">
          <Spinner /> Loading…
        </div>
      </main>
    )

  const { gate } = readiness
  const unanalyzed = inputs.filter((i) => !i.analyzed_at).length
  const staleSections = readiness.sections.filter((s) => s.needs_recheck).length

  return (
    <main className="page">
      <div className="page-head">
        <div style={{ minWidth: 0 }}>
          <div className="breadcrumbs">
            <Link to="/">Research</Link> / <Link to={`/branches/${paper.branch_id}`}>Branch</Link> /{' '}
            {paper.title}
          </div>
          <h1>{paper.title}</h1>
          <div className="row" style={{ marginTop: '0.35rem' }}>
            <span className="muted">
              Research readiness: <strong>{gate.ready_sections}</strong> of{' '}
              {gate.required_sections} sections READY
            </span>
            {gate.open_blockers > 0 && (
              <span className="pill blocker">
                {gate.open_blockers} BLOCKER{gate.open_blockers === 1 ? '' : 'S'}
              </span>
            )}
          </div>
          <div className="readiness-bar" style={{ maxWidth: 420 }}>
            {readiness.sections.map((s) => (
              <i key={s.key} className={s.status} title={`${s.title}: ${s.status}`} />
            ))}
          </div>
        </div>
      </div>

      <div className="row" style={{ marginBottom: '1.1rem' }}>
        <button className="primary" onClick={() => setShowAdd(true)}>
          + Add Research
        </button>
        <button onClick={analyze} disabled={!!busy}>
          {busy === 'Analyzing research…' ? <Spinner /> : null} Analyze research
        </button>
        <button onClick={() => setShowChallenge(true)} disabled={!!busy}>
          Challenge My Research
        </button>
        <button
          onClick={() => setShowManuscript(true)}
          disabled={!!busy || !gate.can_compile}
          title={gate.can_compile ? 'Compile the manuscript' : gate.reasons.join(' ')}
        >
          Compile Manuscript {gate.can_compile ? '' : '🔒'}
        </button>
      </div>

      {busy && (
        <Banner kind="info">
          <Spinner /> {busy} This can take a while — scientific analysis is not optimised for speed.
        </Banner>
      )}
      {error && <Banner kind="error">{error}</Banner>}

      {inputs.length === 0 && (
        <Banner kind="info">
          Nothing added yet. Add anything useful to your research — an idea, notes, papers,
          methodology, experiments, a results CSV. PeerLens builds its understanding from
          whatever you give it.
        </Banner>
      )}

      {unanalyzed > 0 && (
        <Banner kind="warn">
          {unanalyzed} research input{unanalyzed === 1 ? '' : 's'} not yet analyzed.
          Run <strong>Analyze research</strong> to update the checklist.
        </Banner>
      )}

      {staleSections > 0 && unanalyzed === 0 && (
        <Banner kind="warn">
          {staleSections} section{staleSections === 1 ? '' : 's'} need re-checking after recent
          changes. Evidence moved, so what depended on it may no longer hold.
        </Banner>
      )}

      {!gate.can_compile && gate.reasons.length > 0 && (
        <div className="card" style={{ marginTop: '0.85rem' }}>
          <div className="card-title">Compile Manuscript is locked</div>
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {gate.reasons.map((reason) => (
              <li key={reason} className="muted">
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      <h2 style={{ margin: '1.5rem 0 0.6rem' }}>Research Checklist</h2>
      <div className="checklist">
        {readiness.sections.map((section) => {
          const issues = section.issue_counts
          return (
            <button
              key={section.key}
              className="checklist-item"
              onClick={() => setOpenSection(section.key)}
            >
              <StatusIcon status={section.status} />
              <span className="num">{section.number}.</span>
              <span className="title">{section.title}</span>
              <span className="meta">
                {section.needs_recheck && <span className="pill stale">re-check</span>}
                {issues.blocker > 0 && <span className="pill blocker">{issues.blocker} blocker</span>}
                {issues.major > 0 && <span className="pill major">{issues.major} major</span>}
                {issues.minor > 0 && <span className="pill minor">{issues.minor} minor</span>}
                {section.item_count > 0 && (
                  <span className="dim">
                    {section.item_count} item{section.item_count === 1 ? '' : 's'}
                  </span>
                )}
              </span>
            </button>
          )
        })}
      </div>

      <h2 style={{ margin: '1.75rem 0 0.6rem' }}>Research material</h2>
      {inputs.length === 0 ? (
        <p className="dim">Nothing added yet.</p>
      ) : (
        <div className="stack" style={{ gap: '0.5rem' }}>
          {inputs.map((input) => (
            <div className="card" key={input.id} style={{ padding: '0.7rem 0.9rem' }}>
              <div className="row" style={{ gap: '0.5rem' }}>
                <span className="mono dim">#{input.id}</span>
                <strong>{input.label}</strong>
                <span className="dim">
                  {input.kind === 'file' ? input.original_filename : 'text'} ·{' '}
                  {input.char_count.toLocaleString()} chars · {formatDate(input.created_at)}
                </span>
                {!input.analyzed_at && <span className="pill stale">not analyzed</span>}
                <span style={{ marginLeft: 'auto' }}>
                  <button
                    className="small subtle danger"
                    onClick={async () => {
                      if (!confirm(`Delete research input "${input.label}"? The original file is removed too.`))
                        return
                      await api.deleteInput(input.id)
                      load()
                    }}
                  >
                    Delete
                  </button>
                </span>
              </div>
              {input.preview && <p className="dim" style={{ margin: '0.3rem 0 0' }}>{input.preview}</p>}
              {input.extraction_note && (
                <p className="dim" style={{ margin: '0.2rem 0 0', fontStyle: 'italic' }}>
                  {input.extraction_note}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {showAdd && (
        <AddResearchModal
          paperId={id}
          onClose={() => setShowAdd(false)}
          onSaved={async (analyzed) => {
            setShowAdd(false)
            if (analyzed) notifyUsageChanged()
            await load()
          }}
          onAnalyze={analyze}
        />
      )}

      {openSection && (
        <SectionDrawer
          paperId={id}
          sectionKey={openSection}
          onClose={() => setOpenSection(null)}
          onChanged={load}
          onAddResearch={() => {
            setOpenSection(null)
            setShowAdd(true)
          }}
        />
      )}

      {showChallenge && (
        <ChallengeModal paperId={id} onClose={() => setShowChallenge(false)} onChanged={load} />
      )}

      {showManuscript && (
        <ManuscriptModal paperId={id} onClose={() => setShowManuscript(false)} />
      )}
    </main>
  )
}
