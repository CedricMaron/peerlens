import { useRef, useState } from 'react'
import { api } from '../api'
import { Banner, Modal, Spinner, errorMessage } from './common'

const ACCEPT = '.pdf,.txt,.md,.tex,.csv,.json'

/**
 * One universal research input. Deliberately free-form: no scientific form to
 * fill in, because research does not arrive in a structured order.
 */
export default function AddResearchModal({
  paperId,
  onClose,
  onSaved,
  onAnalyze,
}: {
  paperId: number
  onClose: () => void
  onSaved: (analyzed: boolean) => void | Promise<void>
  onAnalyze: () => void | Promise<void>
}) {
  const [label, setLabel] = useState('')
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  const hasContent = text.trim().length > 0 || files.length > 0

  const save = async (thenAnalyze: boolean) => {
    if (!hasContent) return
    setSaving(true)
    setError('')
    try {
      if (text.trim()) {
        await api.addTextInput(paperId, label.trim(), text)
      }
      if (files.length > 0) {
        await api.uploadInputs(paperId, files, files.length === 1 ? label.trim() : '')
      }
      await onSaved(thenAnalyze)
      if (thenAnalyze) await onAnalyze()
    } catch (e) {
      setError(errorMessage(e))
      setSaving(false)
    }
  }

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return
    setFiles((current) => [...current, ...Array.from(incoming)])
  }

  return (
    <Modal title="Add Research" onClose={onClose} wide>
      <p className="muted" style={{ marginTop: '-0.4rem' }}>
        Add anything useful to your research — an idea, notes, literature, methodology,
        experiments, results, observations, draft text, or reviewer feedback. Your original
        input is always kept exactly as you wrote it.
      </p>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="field" style={{ marginTop: '0.9rem' }}>
        <label htmlFor="input-label">Label (optional)</label>
        <input
          id="input-label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="e.g. Day 1 idea, E4 results, reviewer comments"
        />
      </div>

      <div className="field">
        <label htmlFor="input-text">Research input</label>
        <textarea
          id="input-text"
          value={text}
          autoFocus
          onChange={(e) => setText(e.target.value)}
          placeholder={
            'Describe your research idea, or anything you have so far.\n\n' +
            'For example: an idea, a note from a paper, a method, an experiment, ' +
            'a result, a limitation you are worried about.'
          }
          style={{ minHeight: 200 }}
        />
      </div>

      <div
        className={`dropzone${dragging ? ' active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          addFiles(e.dataTransfer.files)
        }}
        onClick={() => fileInput.current?.click()}
        style={{ cursor: 'pointer' }}
      >
        Drop files here or click to browse — PDF, TXT, MD, TEX, CSV, JSON
        <input
          ref={fileInput}
          type="file"
          multiple
          accept={ACCEPT}
          style={{ display: 'none' }}
          onChange={(e) => {
            addFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {files.length > 0 && (
        <div className="row" style={{ marginTop: '0.6rem' }}>
          {files.map((file, index) => (
            <span className="file-chip" key={`${file.name}-${index}`}>
              {file.name}
              <button
                className="subtle small"
                style={{ padding: '0 0.2rem' }}
                onClick={(e) => {
                  e.stopPropagation()
                  setFiles((current) => current.filter((_, i) => i !== index))
                }}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="modal-actions">
        <button onClick={onClose} disabled={saving}>
          Cancel
        </button>
        <button onClick={() => save(false)} disabled={saving || !hasContent} title="Saves without calling the AI">
          {saving ? <Spinner /> : null} Save
        </button>
        <button className="primary" onClick={() => save(true)} disabled={saving || !hasContent}>
          {saving ? <Spinner /> : null} Save &amp; Analyze
        </button>
      </div>
      <p className="dim" style={{ textAlign: 'right', margin: '0.4rem 0 0' }}>
        Save never calls an AI provider. You can add more material over days or months.
      </p>
    </Modal>
  )
}
