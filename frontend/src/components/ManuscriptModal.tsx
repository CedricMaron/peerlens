import { useEffect, useState } from 'react'
import { notifyUsageChanged } from '../App'
import { api } from '../api'
import { Banner, Modal, Spinner, errorMessage, formatDate } from './common'
import type { Manuscript } from '../types'

export default function ManuscriptModal({
  paperId,
  onClose,
}: {
  paperId: number
  onClose: () => void
}) {
  const [manuscripts, setManuscripts] = useState<Manuscript[]>([])
  const [current, setCurrent] = useState<Manuscript | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .listManuscripts(paperId)
      .then((rows) => {
        setManuscripts(rows)
        setCurrent(rows[0] ?? null)
      })
      .catch((e) => setError(errorMessage(e)))
  }, [paperId])

  const compile = async () => {
    setRunning(true)
    setError('')
    try {
      const result = await api.compileManuscript(paperId)
      setCurrent(result)
      setManuscripts((rows) => [result, ...rows])
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setRunning(false)
      notifyUsageChanged()
    }
  }

  const gaps = current?.sections?.content_gaps ?? []

  return (
    <Modal title="Compile Manuscript" onClose={onClose} wide>
      <p className="muted" style={{ marginTop: '-0.4rem' }}>
        Assembled from the reviewed Research State. Nothing is invented: where the research
        does not supply enough material, the gap is reported rather than filled.
      </p>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="row" style={{ margin: '0.9rem 0' }}>
        <button className="primary" onClick={compile} disabled={running}>
          {running ? <Spinner /> : null} {current ? 'Compile again' : 'Compile manuscript'}
        </button>
        {current && (
          <a href={api.manuscriptDownloadUrl(current.id)} download>
            <button>Download Markdown</button>
          </a>
        )}
        {manuscripts.length > 1 && (
          <select
            value={current?.id ?? ''}
            onChange={(e) =>
              setCurrent(manuscripts.find((m) => m.id === Number(e.target.value)) ?? null)
            }
            style={{ width: 'auto' }}
          >
            {manuscripts.map((m) => (
              <option key={m.id} value={m.id}>
                {formatDate(m.created_at)}
              </option>
            ))}
          </select>
        )}
      </div>

      {running && (
        <Banner kind="info">
          <Spinner /> Writing up the reviewed research. This is the longest AI call PeerLens makes.
        </Banner>
      )}

      {gaps.length > 0 && (
        <Banner kind="warn">
          <strong>{gaps.length} content gap{gaps.length === 1 ? '' : 's'} flagged:</strong>
          <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.1rem' }}>
            {gaps.map((gap, index) => (
              <li key={index}>{gap}</li>
            ))}
          </ul>
        </Banner>
      )}

      {current && (
        <div className="card manuscript" style={{ marginTop: '0.85rem' }}>
          <h2 style={{ marginTop: 0 }}>{current.title}</h2>
          {(current.sections?.sections ?? []).map((section, index) => (
            <div key={index}>
              <h3>{section.heading}</h3>
              <pre>{section.markdown}</pre>
            </div>
          ))}
        </div>
      )}

      {!current && !running && (
        <p className="dim">No manuscript compiled yet for this paper project.</p>
      )}
    </Modal>
  )
}
