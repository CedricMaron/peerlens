import { useEffect, type ReactNode } from 'react'
import type { Provenance, Severity, SectionStatus } from '../types'

/** The four checklist states, rendered exactly as the product specifies. */
const STATUS_ICON: Record<SectionStatus, string> = {
  ready: '✓',
  needs_attention: '⚠',
  incomplete: '◐',
  missing: '○',
}

const STATUS_LABEL: Record<SectionStatus, string> = {
  ready: 'READY',
  needs_attention: 'NEEDS ATTENTION',
  incomplete: 'INCOMPLETE',
  missing: 'MISSING',
}

export function StatusIcon({ status }: { status: SectionStatus }) {
  return (
    <span className={`status-icon ${status}`} title={STATUS_LABEL[status]} aria-label={STATUS_LABEL[status]}>
      {STATUS_ICON[status]}
    </span>
  )
}

export function StatusPill({ status }: { status: SectionStatus }) {
  return <span className={`pill ${status}`}>{STATUS_LABEL[status]}</span>
}

export function SeverityPill({ severity }: { severity: Severity }) {
  return <span className={`pill ${severity}`}>{severity.toUpperCase()}</span>
}

const PROVENANCE_HELP: Record<Provenance, string> = {
  provided: 'Directly provided by the researcher or a source',
  extracted: 'Extracted by AI from supplied material',
  inferred: 'AI interpretation — not stated in the material',
  suggested: 'AI suggestion — not part of the research',
}

export function ProvenanceTag({ provenance }: { provenance: Provenance }) {
  return (
    <span className={`prov ${provenance}`} title={PROVENANCE_HELP[provenance]}>
      {provenance}
    </span>
  )
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />
}

export function Banner({
  kind = 'info',
  children,
}: {
  kind?: 'info' | 'error' | 'warn' | 'ok'
  children: ReactNode
}) {
  return <div className={`banner ${kind}`}>{children}</div>
}

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className={`modal${wide ? ' wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="subtle" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

export function formatTokens(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'unknown'
  if (value < 1000) return String(value)
  if (value < 1_000_000) return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}k`
  return `${(value / 1_000_000).toFixed(2)}M`
}

export function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'unknown'
  if (value === 0) return '$0.00'
  if (value < 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(2)}`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return String(error)
}
