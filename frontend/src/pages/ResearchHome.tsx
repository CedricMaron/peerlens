import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Banner, Empty, Modal, Spinner, errorMessage, formatDate } from '../components/common'
import type { Branch } from '../types'

export default function ResearchHome() {
  const [branches, setBranches] = useState<Branch[] | null>(null)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    api
      .listBranches()
      .then(setBranches)
      .catch((e) => setError(errorMessage(e)))
  }

  useEffect(load, [])

  const create = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      await api.createBranch(name.trim(), description)
      setName('')
      setDescription('')
      setCreating(false)
      load()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Research</h1>
          <p className="muted" style={{ marginTop: '0.25rem' }}>
            A research branch groups related papers and shared literature.
          </p>
        </div>
        <div className="spacer" />
        <button className="primary" onClick={() => setCreating(true)}>
          + New Research Branch
        </button>
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      {branches === null && !error && (
        <div className="empty">
          <Spinner /> Loading…
        </div>
      )}

      {branches?.length === 0 && (
        <Empty>
          <p>No research branches yet.</p>
          <p className="dim">
            Start one for a line of research — it can hold several related papers.
          </p>
          <button className="primary" onClick={() => setCreating(true)} style={{ marginTop: '0.5rem' }}>
            + New Research Branch
          </button>
        </Empty>
      )}

      <div className="stack">
        {branches?.map((branch) => (
          <div className="card" key={branch.id}>
            <div className="row" style={{ alignItems: 'baseline' }}>
              <h2>
                <Link to={`/branches/${branch.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                  {branch.name}
                </Link>
              </h2>
              <span className="dim">
                {branch.papers.length} paper{branch.papers.length === 1 ? '' : 's'} ·{' '}
                {branch.literature_count} reference{branch.literature_count === 1 ? '' : 's'}
              </span>
            </div>
            {branch.description && <p className="muted">{branch.description}</p>}
            {branch.papers.length > 0 && (
              <div className="stack" style={{ gap: '0.35rem', marginTop: '0.6rem' }}>
                {branch.papers.map((paper) => (
                  <Link
                    key={paper.id}
                    to={`/papers/${paper.id}`}
                    style={{ textDecoration: 'none', color: 'inherit' }}
                  >
                    <div className="row" style={{ gap: '0.5rem' }}>
                      <span>↳</span>
                      <span style={{ fontWeight: 500 }}>{paper.title}</span>
                      <span className="dim">updated {formatDate(paper.updated_at)}</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
            <div className="row" style={{ marginTop: '0.75rem' }}>
              <Link to={`/branches/${branch.id}`}>
                <button className="small">Open branch</button>
              </Link>
            </div>
          </div>
        ))}
      </div>

      {creating && (
        <Modal title="New Research Branch" onClose={() => setCreating(false)}>
          <div className="field">
            <label htmlFor="branch-name">Name</label>
            <input
              id="branch-name"
              value={name}
              autoFocus
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Urban heat prediction"
            />
          </div>
          <div className="field">
            <label htmlFor="branch-desc">Description (optional)</label>
            <textarea
              id="branch-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this line of research is about."
            />
          </div>
          <div className="modal-actions">
            <button onClick={() => setCreating(false)}>Cancel</button>
            <button className="primary" onClick={create} disabled={saving || !name.trim()}>
              {saving ? <Spinner /> : 'Create branch'}
            </button>
          </div>
        </Modal>
      )}
    </main>
  )
}
