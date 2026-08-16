import { useEffect, useState } from 'react'
import { notifyUsageChanged } from '../App'
import { api } from '../api'
import IssueCard from './IssueCard'
import { Banner, Modal, Spinner, errorMessage } from './common'
import type { ChallengeResult, Issue } from '../types'

/**
 * Challenge My Research: the cross-section review. Runs on demand and is
 * always available, whatever state the research is in.
 */
export default function ChallengeModal({
  paperId,
  onClose,
  onChanged,
}: {
  paperId: number
  onClose: () => void
  onChanged: () => void | Promise<void>
}) {
  const [result, setResult] = useState<ChallengeResult | null>(null)
  const [previous, setPrevious] = useState<Issue[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .listIssues(paperId)
      .then((issues) => setPrevious(issues.filter((i) => i.origin === 'challenge')))
      .catch(() => setPrevious([]))
  }, [paperId])

  const run = async () => {
    setRunning(true)
    setError('')
    try {
      setResult(await api.challenge(paperId))
      await onChanged()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setRunning(false)
      notifyUsageChanged()
    }
  }

  const issues = result?.issues ?? previous
  const blockers = issues.filter((i) => i.severity === 'blocker').length

  return (
    <Modal title="Challenge My Research" onClose={onClose} wide>
      <p className="muted" style={{ marginTop: '-0.4rem' }}>
        A cross-section scientific review. It traces each claim back through findings,
        results, experiments and methodology, and reports where the chain breaks — most
        important first.
      </p>

      {error && <Banner kind="error">{error}</Banner>}

      <div className="row" style={{ margin: '0.9rem 0' }}>
        <button className="primary" onClick={run} disabled={running}>
          {running ? <Spinner /> : null} {result || previous.length > 0 ? 'Run again' : 'Run challenge'}
        </button>
        {running && <span className="dim">This is a deep review and can take a while.</span>}
      </div>

      {result?.overall_assessment && (
        <div className="card" style={{ marginBottom: '0.85rem' }}>
          <div className="card-title">Overall assessment</div>
          <p style={{ margin: 0 }}>{result.overall_assessment}</p>
        </div>
      )}

      {!result && previous.length > 0 && (
        <Banner kind="info">
          Showing issues from the previous challenge. Run again to re-assess against the
          current research state.
        </Banner>
      )}

      {issues.length > 0 && (
        <>
          <div className="row" style={{ margin: '0.9rem 0 0.6rem' }}>
            <h3>
              {issues.length} issue{issues.length === 1 ? '' : 's'}
            </h3>
            {blockers > 0 && <span className="pill blocker">{blockers} blocker</span>}
          </div>
          <div className="stack" style={{ gap: '0.6rem' }}>
            {issues.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                onChanged={async () => {
                  const refreshed = await api.listIssues(paperId)
                  const challengeIssues = refreshed.filter((i) => i.origin === 'challenge')
                  setPrevious(challengeIssues)
                  if (result) setResult({ ...result, issues: challengeIssues })
                  await onChanged()
                }}
              />
            ))}
          </div>
        </>
      )}

      {result && issues.length === 0 && (
        <Banner kind="ok">
          The cross-section review raised no issues against the research currently supplied.
          This reflects the material PeerLens has, not an independent verification of the work.
        </Banner>
      )}

      {result && result.cross_section_observations.length > 0 && (
        <div className="card" style={{ marginTop: '0.85rem' }}>
          <div className="card-title">Cross-section observations</div>
          <ul style={{ margin: 0, paddingLeft: '1.1rem' }}>
            {result.cross_section_observations.map((observation, index) => (
              <li key={index} className="muted">
                {observation}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Modal>
  )
}
