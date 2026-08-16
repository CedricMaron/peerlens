import { useState } from 'react'
import { api } from '../api'
import { SeverityPill, errorMessage } from './common'
import type { Issue } from '../types'

export default function IssueCard({
  issue,
  onChanged,
  showSections = true,
}: {
  issue: Issue
  onChanged: () => void | Promise<void>
  showSections?: boolean
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const setStatus = async (status: 'resolved' | 'dismissed') => {
    setBusy(true)
    try {
      await api.updateIssue(issue.id, status)
      await onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`issue ${issue.severity}`}>
      <div className="row">
        <SeverityPill severity={issue.severity} />
        {issue.origin === 'challenge' && <span className="dim">from Challenge</span>}
        {showSections && issue.affected_sections.length > 0 && (
          <span className="dim">Affects: {issue.affected_sections.join(', ')}</span>
        )}
      </div>
      <h4>{issue.issue}</h4>
      <dl>
        {issue.why_it_matters && (
          <>
            <dt>Why it matters</dt>
            <dd>{issue.why_it_matters}</dd>
          </>
        )}
        {issue.evidence && (
          <>
            <dt>Evidence</dt>
            <dd>{issue.evidence}</dd>
          </>
        )}
        {issue.recommended_action && (
          <>
            <dt>Action</dt>
            <dd>{issue.recommended_action}</dd>
          </>
        )}
      </dl>
      {error && <div className="dim" style={{ color: 'var(--blocker)' }}>{error}</div>}
      <div className="item-actions">
        <button className="small" onClick={() => setStatus('resolved')} disabled={busy}>
          Mark resolved
        </button>
        <button
          className="small subtle"
          onClick={() => setStatus('dismissed')}
          disabled={busy}
          title="Dismissed issues are not raised again by later reviews"
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}
