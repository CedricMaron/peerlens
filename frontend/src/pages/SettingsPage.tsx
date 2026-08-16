import { useEffect, useState } from 'react'
import { api } from '../api'
import { Banner, Spinner, errorMessage } from '../components/common'
import type { ProviderSettings } from '../types'

type ProviderName = 'openai' | 'anthropic' | 'ollama'

const PROVIDER_INFO: Record<ProviderName, { label: string; blurb: string; needsKey: boolean }> = {
  openai: {
    label: 'OpenAI',
    blurb: 'Cloud models via the OpenAI API. Your key is stored on this machine only.',
    needsKey: true,
  },
  anthropic: {
    label: 'Anthropic',
    blurb: 'Claude models via the Anthropic API. Your key is stored on this machine only.',
    needsKey: true,
  },
  ollama: {
    label: 'Ollama (local)',
    blurb: 'Runs entirely on your own hardware. No API key, no data leaves your machine.',
    needsKey: false,
  },
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<ProviderSettings | null>(null)
  const [provider, setProvider] = useState<ProviderName>('ollama')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  const applySettings = (value: ProviderSettings) => {
    setSettings(value)
    const name = (value.provider || 'ollama') as ProviderName
    setProvider(name)
    setModel(value.model || value.defaults.models[name] || '')
    setBaseUrl(value.base_url || value.defaults.base_urls[name] || '')
  }

  useEffect(() => {
    api
      .getProvider()
      .then(applySettings)
      .catch((e) => setError(errorMessage(e)))
  }, [])

  useEffect(() => {
    if (provider !== 'ollama') return
    api
      .ollamaModels(baseUrl || undefined)
      .then(setOllamaModels)
      .catch(() => setOllamaModels([]))
  }, [provider, baseUrl])

  const switchProvider = (name: ProviderName) => {
    setProvider(name)
    setTestResult(null)
    setSaved(false)
    setApiKey('')
    if (settings) {
      const isCurrent = settings.provider === name
      setModel(isCurrent ? settings.model : settings.defaults.models[name] || '')
      setBaseUrl(isCurrent ? settings.base_url : settings.defaults.base_urls[name] || '')
    }
  }

  const test = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      setTestResult(
        await api.testProvider({
          provider,
          model,
          api_key: apiKey || undefined,
          base_url: baseUrl || undefined,
        }),
      )
    } catch (e) {
      setTestResult({ ok: false, message: errorMessage(e) })
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      applySettings(
        await api.saveProvider({
          provider,
          model,
          api_key: apiKey || undefined,
          base_url: baseUrl || undefined,
        }),
      )
      setApiKey('')
      setSaved(true)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  const info = PROVIDER_INFO[provider]

  return (
    <main className="page narrow">
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <p className="muted">Connect the AI provider PeerLens uses for scientific analysis.</p>
        </div>
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      {settings && (
        <div className="card" style={{ marginBottom: '0.85rem' }}>
          <div className="card-title">Active provider</div>
          {settings.configured ? (
            <div className="row">
              <span className="pill ready">CONNECTED</span>
              <strong>{PROVIDER_INFO[(settings.provider as ProviderName) ?? 'ollama']?.label ?? settings.provider}</strong>
              <span className="mono">{settings.model}</span>
              {settings.from_environment && <span className="dim">from environment variables</span>}
            </div>
          ) : (
            <div className="row">
              <span className="pill missing">NOT CONFIGURED</span>
              <span className="muted">
                Choose a provider below. PeerLens cannot analyze research without one.
              </span>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <div className="card-title">AI Provider</div>

        <div className="row" style={{ marginBottom: '1rem' }}>
          {(Object.keys(PROVIDER_INFO) as ProviderName[]).map((name) => (
            <button
              key={name}
              className={provider === name ? 'primary' : ''}
              onClick={() => switchProvider(name)}
            >
              {PROVIDER_INFO[name].label}
            </button>
          ))}
        </div>

        <p className="dim">{info.blurb}</p>

        {info.needsKey && (
          <div className="field">
            <label htmlFor="api-key">API key</label>
            <input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={
                settings?.api_key_set && settings.provider === provider
                  ? `Saved (${settings.api_key_hint}) — leave blank to keep it`
                  : provider === 'openai'
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
          <label htmlFor="model">Model</label>
          {provider === 'ollama' && ollamaModels.length > 0 ? (
            <>
              <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
                {!ollamaModels.includes(model) && model && <option value={model}>{model}</option>}
                {ollamaModels.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <p className="dim" style={{ marginTop: '0.3rem' }}>
                {ollamaModels.length} model{ollamaModels.length === 1 ? '' : 's'} installed locally.
              </p>
            </>
          ) : (
            <input id="model" value={model} onChange={(e) => setModel(e.target.value)} />
          )}
        </div>

        <div className="field">
          <label htmlFor="base-url">
            {provider === 'ollama' ? 'Ollama base URL' : 'Base URL (optional)'}
          </label>
          <input id="base-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          {provider === 'ollama' && (
            <p className="dim" style={{ marginTop: '0.3rem' }}>
              Running PeerLens in Docker? Use <span className="mono">http://host.docker.internal:11434</span>{' '}
              to reach Ollama on the host.
            </p>
          )}
        </div>

        <div className="row">
          <button onClick={test} disabled={testing || !model}>
            {testing ? <Spinner /> : null} Test Connection
          </button>
          <button className="primary" onClick={save} disabled={saving || !model}>
            {saving ? <Spinner /> : null} Save
          </button>
          {settings?.api_key_set && info.needsKey && (
            <button
              className="subtle danger"
              onClick={async () => {
                if (!confirm('Remove the stored API key?')) return
                applySettings(await api.clearApiKey())
              }}
            >
              Remove stored key
            </button>
          )}
        </div>

        {saved && <Banner kind="ok">Settings saved.</Banner>}
        {testResult && (
          <div style={{ marginTop: '0.7rem' }}>
            <Banner kind={testResult.ok ? 'ok' : 'error'}>{testResult.message}</Banner>
          </div>
        )}
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
