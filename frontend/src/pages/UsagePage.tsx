import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  Banner,
  Empty,
  Spinner,
  errorMessage,
  formatCost,
  formatDate,
  formatTokens,
} from '../components/common'
import type { UsageOverview, UsageRow } from '../types'

const DIMENSIONS = [
  { key: 'by_operation', label: 'Operation' },
  { key: 'by_paper', label: 'Paper' },
  { key: 'by_branch', label: 'Research branch' },
  { key: 'by_model', label: 'Model' },
  { key: 'by_provider', label: 'Provider' },
  { key: 'by_location', label: 'Cloud vs local' },
] as const

function BreakdownTable({ rows }: { rows: UsageRow[] }) {
  if (rows.length === 0) return <p className="dim">No calls recorded.</p>
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th className="num">Calls</th>
            <th className="num">Input</th>
            <th className="num">Output</th>
            <th className="num">Total</th>
            <th className="num">Est. cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>{row.key}</td>
              <td className="num">{row.calls}</td>
              <td className="num">{formatTokens(row.input_tokens)}</td>
              <td className="num">{formatTokens(row.output_tokens)}</td>
              <td className="num">{formatTokens(row.total_tokens)}</td>
              <td className="num">{formatCost(row.estimated_cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function UsagePage() {
  const [usage, setUsage] = useState<UsageOverview | null>(null)
  const [error, setError] = useState('')
  const [dimension, setDimension] = useState<(typeof DIMENSIONS)[number]['key']>('by_operation')

  useEffect(() => {
    api
      .getUsage()
      .then(setUsage)
      .catch((e) => setError(errorMessage(e)))
  }, [])

  if (error) return <main className="page"><Banner kind="error">{error}</Banner></main>
  if (!usage)
    return (
      <main className="page">
        <div className="empty">
          <Spinner /> Loading…
        </div>
      </main>
    )

  const { totals } = usage

  return (
    <main className="page">
      <div className="page-head">
        <div>
          <h1>Usage</h1>
          <p className="muted">
            Every AI call PeerLens makes. Values the provider did not report are shown as
            unknown, never estimated.
          </p>
        </div>
      </div>

      {totals.calls === 0 ? (
        <Empty>
          No AI calls yet. Usage appears here once you analyze research.
        </Empty>
      ) : (
        <>
          <div className="stats">
            <div className="stat">
              <div className="label">Total tokens</div>
              <div className="value">{formatTokens(totals.total_tokens)}</div>
              <div className="sub">{totals.calls} calls</div>
            </div>
            <div className="stat">
              <div className="label">Input tokens</div>
              <div className="value">{formatTokens(totals.input_tokens)}</div>
              {totals.cached_tokens ? (
                <div className="sub">{formatTokens(totals.cached_tokens)} cached</div>
              ) : null}
            </div>
            <div className="stat">
              <div className="label">Output tokens</div>
              <div className="value">{formatTokens(totals.output_tokens)}</div>
            </div>
            <div className="stat">
              <div className="label">Estimated cost</div>
              <div className="value">{formatCost(totals.estimated_cost)}</div>
              <div className="sub">
                {totals.calls_with_unknown_cost > 0
                  ? `${totals.calls_with_unknown_cost} call(s) with unknown pricing`
                  : 'all calls priced'}
              </div>
            </div>
            <div className="stat">
              <div className="label">Avg latency</div>
              <div className="value">
                {totals.avg_latency_ms === null ? '—' : `${(totals.avg_latency_ms / 1000).toFixed(1)}s`}
              </div>
              {totals.failed_calls > 0 && (
                <div className="sub" style={{ color: 'var(--blocker)' }}>
                  {totals.failed_calls} failed
                </div>
              )}
            </div>
          </div>

          <h2 style={{ margin: '1.75rem 0 0.6rem' }}>Breakdown</h2>
          <div className="tabs">
            {DIMENSIONS.map((entry) => (
              <button
                key={entry.key}
                className={dimension === entry.key ? 'active' : ''}
                onClick={() => setDimension(entry.key)}
              >
                {entry.label}
              </button>
            ))}
          </div>
          <div className="card">
            <BreakdownTable rows={usage[dimension]} />
          </div>

          <h2 style={{ margin: '1.75rem 0 0.6rem' }}>Recent calls</h2>
          <div className="card">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Operation</th>
                    <th>Model</th>
                    <th className="num">In</th>
                    <th className="num">Out</th>
                    <th className="num">Latency</th>
                    <th className="num">Cost</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {usage.recent.map((event) => (
                    <tr key={event.id}>
                      <td className="dim">{formatDate(event.created_at)}</td>
                      <td className="mono">{event.operation}</td>
                      <td className="mono">
                        {event.model}
                        {event.is_local && <span className="dim"> (local)</span>}
                      </td>
                      <td className="num">{formatTokens(event.input_tokens)}</td>
                      <td className="num">{formatTokens(event.output_tokens)}</td>
                      <td className="num">
                        {event.latency_ms === null ? '—' : `${(event.latency_ms / 1000).toFixed(1)}s`}
                      </td>
                      <td className="num">{formatCost(event.estimated_cost)}</td>
                      <td>
                        {!event.success && (
                          <span className="pill blocker" title={event.error ?? ''}>
                            FAILED
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </main>
  )
}
