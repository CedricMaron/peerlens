import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Banner, Spinner, errorMessage } from '../components/common'
import type { LoginStatus, ProviderStatus } from '../types'

/** What the three status words mean per provider kind. */
function statusChips(p: ProviderStatus) {
  const chips: { label: string; on: boolean }[] = []
  if (p.kind === 'cli') {
    chips.push({ label: p.installed ? 'Installed' : 'Not installed', on: !!p.installed })
    if (p.installed) {
      if (p.authenticated === true) chips.push({ label: 'Connected', on: true })
      else if (p.authenticated === false) chips.push({ label: 'Not connected', on: false })
      else chips.push({ label: 'Connection state unknown', on: false })
    }
  } else if (p.kind === 'local') {
    chips.push({ label: p.state === 'unavailable' ? 'Not running' : 'Running', on: p.state !== 'unavailable' })
    if (p.state !== 'unavailable') {
      chips.push({ label: p.model ? `Model ${p.model}` : 'No model selected', on: !!p.model })
    }
  } else {
    chips.push({ label: p.api_key_set ? 'Configured' : 'Not configured', on: p.api_key_set })
  }
  return chips
}

function actionLabel(p: ProviderStatus) {
  if (p.id === 'claude-code') return 'Use Claude Code'
  if (p.id === 'codex') return 'Use Codex'
  if (p.id === 'ollama') return 'Use Ollama'
  return `Use ${p.label}`
}

export default function SettingsPage() {
  const [providers, setProviders] = useState<ProviderStatus[]>([])
  const [activeProvider, setActiveProvider] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [logins, setLogins] = useState<Record<string, LoginStatus>>({})
  const pollers = useRef<Record<string, number>>({})

  const refresh = useCallback(async () => {
    try {
      const data = await api.listProviders()
      setProviders(data.providers)
      setActiveProvider(data.active_provider)
      setError('')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const timers = pollers.current
    return () => Object.values(timers).forEach((t) => window.clearInterval(t))
  }, [refresh])

  const use = async (id: string) => {
    setNotice('')
    try {
      await api.selectProvider(id)
      await refresh()
      setNotice(`PeerLens will now use ${providers.find((p) => p.id === id)?.label ?? id}.`)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  const connect = async (id: string) => {
    setNotice('')
    try {
      const status = await api.startLogin(id)
      setLogins((current) => ({ ...current, [id]: status }))
      if (!status.running) return
      window.clearInterval(pollers.current[id])
      pollers.current[id] = window.setInterval(async () => {
        const next = await api.loginStatus(id)
        setLogins((current) => ({ ...current, [id]: next }))
        if (!next.running) {
          window.clearInterval(pollers.current[id])
          delete pollers.current[id]
          refresh()
        }
      }, 2000)
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  const cancelLogin = async (id: string) => {
    window.clearInterval(pollers.current[id])
    delete pollers.current[id]
    const status = await api.cancelLogin(id)
    setLogins((current) => ({ ...current, [id]: status }))
    refresh()
  }

  const active = providers.find((p) => p.id === activeProvider)

  return (
    <main className="page narrow">
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="muted">Connect the AI provider PeerLens uses for scientific analysis.</p>
        </div>
      </div>

      {error && <Banner kind="error">{error}</Banner>}
      {notice && <Banner kind="ok">{notice}</Banner>}

      <div className="card" style={{ marginBottom: '0.85rem' }}>
        <div className="card-title">Current AI provider</div>
        {active ? (
          <div className="row">
            <span className={`pill ${active.available ? 'ready' : 'needs_attention'}`}>
              {active.available ? 'READY' : active.state.replace(/_/g, ' ').toUpperCase()}
            </span>
            <strong>{active.label}</strong>
            {active.model && <span className="mono">{active.model}</span>}
            {active.is_local && <span className="dim">local — nothing leaves this machine</span>}
            {active.is_subscription && (
              <span className="dim">uses your account through the official CLI</span>
            )}
          </div>
        ) : (
          <div className="row">
            <span className="pill missing">NOT CONFIGURED</span>
            <span className="muted">
              No AI provider configured. Choose one below: Claude Code, OpenAI Codex,
              Anthropic API, OpenAI API, or a local Ollama model.
            </span>
          </div>
        )}
        {active && !active.available && active.message && (
          <p className="dim" style={{ marginTop: '0.4rem' }}>{active.message}</p>
        )}
        <p className="dim" style={{ marginTop: '0.5rem' }}>
          PeerLens never falls back to another provider on its own. If the selected provider
          fails, the request fails — your unpublished research is not sent elsewhere.
        </p>
      </div>

      <div className="card">
        <div className="card-title">AI Provider</div>
        {loading ? (
          <div className="empty"><Spinner /> Detecting providers…</div>
        ) : (
          <div className="stack" style={{ gap: '0.6rem' }}>
            {providers.map((p) => (
              <ProviderRow
                key={p.id}
                provider={p}
                login={logins[p.id]}
                editing={editing === p.id}
                onToggleEdit={() => setEditing(editing === p.id ? null : p.id)}
                onUse={() => use(p.id)}
                onConnect={() => connect(p.id)}
                onCancelLogin={() => cancelLogin(p.id)}
                onSaved={refresh}
              />
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">How provider accounts work</div>
        <p className="muted">
          Claude and ChatGPT subscriptions and API billing are separate systems. Claude Code
          and Codex use your existing subscription through the official CLI, which owns the
          sign-in: PeerLens never asks for a Claude or ChatGPT password, never reads a
          credential file, and never stores a session token. API keys are stored server-side
          in your local database, shown only as a masked hint, and never logged. Running
          Ollama keeps model inference entirely on your machine.
        </p>
      </div>

      <div className="card">
        <div className="card-title">Scientific limitations</div>
        <p className="muted">
          PeerLens does not replace scientific judgment or peer review. It reasons only over
          the material you supply, its literature coverage is limited to what you add, and
          language models can be wrong. Treat everything it produces as a prompt for your own
          judgment — especially when it agrees with you.
        </p>
      </div>
    </main>
  )
}

function ProviderRow({
  provider,
  login,
  editing,
  onToggleEdit,
  onUse,
  onConnect,
  onCancelLogin,
  onSaved,
}: {
  provider: ProviderStatus
  login?: LoginStatus
  editing: boolean
  onToggleEdit: () => void
  onUse: () => void
  onConnect: () => void
  onCancelLogin: () => void
  onSaved: () => void
}) {
  const p = provider
  const needsSetup = p.needs_api_key || p.requires_model || p.kind === 'cli'

  return (
    <div className="card" style={{ padding: '0.8rem 0.9rem' }}>
      <div className="row">
        <strong>{p.label}</strong>
        {p.is_active && <span className="pill ready">ACTIVE</span>}
        {p.version && <span className="dim mono">{p.version}</span>}
        <span className="row" style={{ marginLeft: 'auto', gap: '0.4rem' }}>
          {p.supports_login && p.installed && (
            <button className="small" onClick={onConnect}>
              {p.authenticated === true ? 'Reconnect' : 'Connect'}
            </button>
          )}
          {needsSetup && (
            <button className="small" onClick={onToggleEdit}>
              {editing ? 'Close' : p.needs_api_key && !p.api_key_set ? 'Configure' : 'Settings'}
            </button>
          )}
          {!p.is_active && (
            <button className="small primary" onClick={onUse} disabled={!p.configured}>
              {actionLabel(p)}
            </button>
          )}
        </span>
      </div>

      <div className="row" style={{ gap: '0.75rem', marginTop: '0.35rem' }}>
        {statusChips(p).map((chip) => (
          <span key={chip.label} className="dim">
            <span style={{ color: chip.on ? 'var(--ready)' : 'var(--text-3)' }}>
              {chip.on ? '●' : '○'}
            </span>{' '}
            {chip.label}
          </span>
        ))}
      </div>

      <p className="dim" style={{ margin: '0.35rem 0 0' }}>{p.blurb}</p>
      {p.message && <p className="dim" style={{ margin: '0.25rem 0 0' }}>{p.message}</p>}
      {p.installed === false && (
        <p className="dim" style={{ margin: '0.25rem 0 0' }}>{p.setup_hint}</p>
      )}

      {login && login.state !== 'IDLE' && (
        <div style={{ marginTop: '0.5rem' }}>
          <Banner
            kind={
              login.state === 'LOGIN_SUCCESS'
                ? 'ok'
                : login.state === 'LOGIN_STARTED' || login.state === 'LOGIN_ALREADY_RUNNING'
                  ? 'info'
                  : 'warn'
            }
          >
            <span className="mono">{login.state}</span> — {login.message}
            {login.url && (
              <>
                {' '}
                <a href={login.url} target="_blank" rel="noreferrer">
                  Open the sign-in page
                </a>
              </>
            )}
            {login.running && (
              <>
                {' '}
                <button className="small subtle" onClick={onCancelLogin}>
                  Cancel
                </button>
              </>
            )}
          </Banner>
        </div>
      )}

      {editing && <ProviderForm provider={p} onSaved={onSaved} />}
    </div>
  )
}

function ProviderForm({ provider, onSaved }: { provider: ProviderStatus; onSaved: () => void }) {
  const p = provider
  const [model, setModel] = useState(p.model)
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState(p.base_url)
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (p.id !== 'ollama') return
    api.ollamaModels(baseUrl || undefined).then(setOllamaModels).catch(() => setOllamaModels([]))
  }, [p.id, baseUrl])

  const test = async () => {
    setTesting(true)
    setResult(null)
    try {
      setResult(
        await api.testProvider({
          provider: p.id,
          model,
          api_key: apiKey || undefined,
          base_url: baseUrl || undefined,
        }),
      )
    } catch (e) {
      setResult({ ok: false, message: errorMessage(e) })
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setSaved(false)
    try {
      await api.saveProvider({
        provider: p.id,
        model,
        api_key: apiKey || undefined,
        base_url: baseUrl || undefined,
        // Configuring a provider never switches to it: "Use <provider>" does.
        make_active: p.is_active,
      })
      setApiKey('')
      setSaved(true)
      onSaved()
    } catch (e) {
      setResult({ ok: false, message: errorMessage(e) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ marginTop: '0.7rem', borderTop: '1px solid var(--border)', paddingTop: '0.7rem' }}>
      <p className="dim" style={{ marginTop: 0 }}>{p.setup_hint}</p>

      {p.needs_api_key && (
        <div className="field">
          <label htmlFor={`key-${p.id}`}>API key</label>
          <input
            id={`key-${p.id}`}
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              p.api_key_set
                ? `Saved (${p.api_key_hint}) — leave blank to keep it`
                : p.id === 'openai'
                  ? 'sk-…'
                  : 'sk-ant-…'
            }
            autoComplete="off"
          />
          <p className="dim" style={{ marginTop: '0.3rem' }}>
            Stored server-side in your local database. It is never sent to the browser,
            never logged, and never written to browser storage.
          </p>
        </div>
      )}

      <div className="field">
        <label htmlFor={`model-${p.id}`}>
          {p.requires_model ? 'Model' : 'Model (optional)'}
        </label>
        {p.id === 'ollama' && ollamaModels.length > 0 ? (
          <select id={`model-${p.id}`} value={model} onChange={(e) => setModel(e.target.value)}>
            {!ollamaModels.includes(model) && model && <option value={model}>{model}</option>}
            {ollamaModels.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        ) : (
          <input
            id={`model-${p.id}`}
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={p.requires_model ? '' : `Leave blank to use the ${p.label} default`}
          />
        )}
      </div>

      {p.kind !== 'cli' && (
        <div className="field">
          <label htmlFor={`url-${p.id}`}>
            {p.id === 'ollama' ? 'Ollama base URL' : 'Base URL (optional)'}
          </label>
          <input id={`url-${p.id}`} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          {p.id === 'ollama' && (
            <p className="dim" style={{ marginTop: '0.3rem' }}>
              Running PeerLens in Docker? Use{' '}
              <span className="mono">http://host.docker.internal:11434</span> to reach Ollama
              on the host.
            </p>
          )}
        </div>
      )}

      <div className="row">
        <button onClick={test} disabled={testing || (p.requires_model && !model)}>
          {testing ? <Spinner /> : null} Test Connection
        </button>
        <button
          className="primary"
          onClick={save}
          disabled={saving || (p.requires_model && !model)}
        >
          {saving ? <Spinner /> : null} Save
        </button>
        {p.api_key_set && p.needs_api_key && (
          <button
            className="subtle danger"
            onClick={async () => {
              if (!confirm(`Remove the stored ${p.label} key?`)) return
              await api.clearApiKey(p.id)
              onSaved()
            }}
          >
            Remove stored key
          </button>
        )}
      </div>

      {saved && <Banner kind="ok">Settings saved.</Banner>}
      {result && (
        <div style={{ marginTop: '0.7rem' }}>
          <Banner kind={result.ok ? 'ok' : 'error'}>{result.message}</Banner>
        </div>
      )}
    </div>
  )
}
