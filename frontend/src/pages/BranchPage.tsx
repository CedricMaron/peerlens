import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { Banner, Empty, Modal, Spinner, errorMessage } from '../components/common'
import LiteraturePanel from '../components/LiteraturePanel'
import type { Branch } from '../types'

export default function BranchPage() {
  const { branchId } = useParams()
  const id = Number(branchId)
  const [branch, setBranch] = useState<Branch | null>(null)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'papers' | 'literature'>('papers')
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    api
      .getBranch(id)
      .then(setBranch)
      .catch((e) => setError(errorMessage(e)))
  }, [id])

  useEffect(load, [load])

  const createPaper = async () => {
    if (!title.trim()) return
    setSaving(true)
    try {
      await api.createPaper(id, title.trim())
      setTitle('')
      setCreating(false)
      load()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  if (error) return <main className="page"><Banner kind="error">{error}</Banner></main>
  if (!branch)
    return (
      <main className="page">
        <div className="empty">
          <Spinner /> Loading…
        </div>
      </main>
    )

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <div className="breadcrumbs">
            <Link to="/">Research</Link> / {branch.name}
          </div>
          <h1>{branch.name}</h1>
          {branch.description && <p className="muted">{branch.description}</p>}
        </div>
        <div className="spacer" />
        {tab === 'papers' && (
          <button className="primary" onClick={() => setCreating(true)}>
            + New Paper Project
          </button>
        )}
      </div>

      <div className="tabs">
        <button className={tab === 'papers' ? 'active' : ''} onClick={() => setTab('papers')}>
          Paper projects ({branch.papers.length})
        </button>
        <button className={tab === 'literature' ? 'active' : ''} onClick={() => setTab('literature')}>
          Literature ({branch.literature_count})
        </button>
      </div>

      {tab === 'papers' && (
        <>
          {branch.papers.length === 0 ? (
            <Empty>
              <p>No paper projects in this branch yet.</p>
              <p className="dim">A branch can hold several related papers sharing this literature.</p>
              <button className="primary" onClick={() => setCreating(true)} style={{ marginTop: '0.5rem' }}>
                + New Paper Project
              </button>
            </Empty>
          ) : (
            <div className="stack">
              {branch.papers.map((paper) => (
                <Link
                  key={paper.id}
                  to={`/papers/${paper.id}`}
                  style={{ textDecoration: 'none', color: 'inherit' }}
                >
                  <div className="card">
                    <h2>{paper.title}</h2>
                    {paper.notes && <p className="muted">{paper.notes}</p>}
                    <span className="dim">Open the research checklist →</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'literature' && <LiteraturePanel branchId={id} onChange={load} />}

      {creating && (
        <Modal title="New Paper Project" onClose={() => setCreating(false)}>
          <div className="field">
            <label htmlFor="paper-title">Working title</label>
            <input
              id="paper-title"
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Class-specialized teachers for federated distillation"
            />
            <p className="dim" style={{ marginTop: '0.4rem' }}>
              You can change this at any time. Nothing else is required to start.
            </p>
          </div>
          <div className="modal-actions">
            <button onClick={() => setCreating(false)}>Cancel</button>
            <button className="primary" onClick={createPaper} disabled={saving || !title.trim()}>
              {saving ? <Spinner /> : 'Create paper project'}
            </button>
          </div>
        </Modal>
      )}
    </main>
  )
}
