import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button, Result, Spin, Splitter, Tag, message } from 'antd'
import { api, type GitStatus, type Project } from '../api/client'

export function WorkspacePage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const id = params.get('id') ?? ''
  const [project, setProject] = useState<Project | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pickMode, setPickMode] = useState(false)
  const [copyToast, setCopyToast] = useState<string | null>(null)
  const [previewReady, setPreviewReady] = useState(false)
  const [bootElapsed, setBootElapsed] = useState(0)
  const [iframeKey, setIframeKey] = useState(0)
  const previewRef = useRef<HTMLIFrameElement | null>(null)

  const [status, setStatus] = useState<GitStatus | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [messageApi, contextHolder] = message.useMessage()

  useEffect(() => {
    if (!id) { navigate('/'); return }
    api.getProject(id)
      .then(setProject)
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
  }, [id, navigate])

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (!e.data || typeof e.data !== 'object') return
      if (e.data.type === 'lingua:selection') {
        setPickMode(false)
        setCopyToast(e.data.summary ?? 'Copied')
        setTimeout(() => setCopyToast(null), 3000)
      } else if (e.data.type === 'lingua:cancel') {
        setPickMode(false)
      }
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  useEffect(() => {
    const iframe = previewRef.current
    if (!iframe) return
    const msg = pickMode ? { type: 'lingua:enable_pick' } : { type: 'lingua:disable' }
    try {
      iframe.contentWindow?.postMessage(msg, '*')
    } catch {}
  }, [pickMode])

  useEffect(() => {
    if (previewReady) return
    let cancelled = false
    const startedAt = Date.now()
    const tick = async () => {
      try {
        const r = await fetch('/preview/', { method: 'HEAD', cache: 'no-store' })
        if (!cancelled && r.ok) {
          setPreviewReady(true)
          setIframeKey(k => k + 1)
          return
        }
      } catch {}
      if (!cancelled) setBootElapsed(Math.floor((Date.now() - startedAt) / 1000))
    }
    tick()
    const pollId = setInterval(tick, 2000)
    return () => { cancelled = true; clearInterval(pollId) }
  }, [previewReady])

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const s = await api.gitStatus()
        if (!cancelled) setStatus(s)
      } catch {}
    }
    poll()
    const pollId = setInterval(poll, 5000)
    return () => { cancelled = true; clearInterval(pollId) }
  }, [])

  const onPreviewLoad = () => {
    const iframe = previewRef.current
    if (!iframe) return
    try {
      const doc = iframe.contentDocument
      if (!doc) return
      if (doc.getElementById('lingua-picker-script')) return
      const s = doc.createElement('script')
      s.id = 'lingua-picker-script'
      s.type = 'module'
      s.src = `${window.location.origin}/lingua-picker.js`
      doc.body.appendChild(s)
    } catch (err) {
      console.warn('lingua-picker: contentDocument access failed', err)
    }
  }

  const publish = async () => {
    setPublishing(true)
    try {
      const r = await api.gitPublish()
      if (r.ok) {
        messageApi.success(`Pushed: ${r.branch}`)
      } else {
        messageApi.error(`Error: ${r.error ?? r.step}`)
      }
    } catch (e) {
      messageApi.error(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setPublishing(false)
    }
  }

  const branchLabel = status?.ok
    ? `⎇ ${status.branch}${status.ahead ? ` · ${status.ahead} ahead` : ''}${status.no_upstream ? ' · no upstream' : ''}`
    : '⎇ —'

  if (error) {
    return (
      <Result
        status="error"
        title={error}
        extra={<Button onClick={() => navigate('/')}>Back</Button>}
      />
    )
  }

  if (!project) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', marginTop: 80 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {contextHolder}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px', borderBottom: '1px solid rgba(128,128,128,0.2)', flexShrink: 0 }}>
        <Button size="small" onClick={() => navigate('/')}>← Back</Button>
        <span style={{ fontWeight: 600, fontSize: 14 }}>{project.name}</span>
        <Tag>{branchLabel}</Tag>
        {status?.dirty_files ? <Tag color="warning">{status.dirty_files} unsaved</Tag> : null}
        <div style={{ flex: 1 }} />
        {copyToast && <Tag color="success">{copyToast} ✓ paste into chat</Tag>}
        <Button
          size="small"
          type={pickMode ? 'primary' : 'default'}
          onClick={() => setPickMode(v => !v)}
        >
          {pickMode ? 'Picking… (ESC)' : 'Select'}
        </Button>
        <Button size="small" type="primary" loading={publishing} onClick={publish}>
          Publish
        </Button>
      </div>

      <Splitter style={{ flex: 1, minHeight: 0 }}>
        <Splitter.Panel defaultSize="50%" min="20%">
          <iframe
            src={`http://${window.location.hostname}:8000`}
            title="Chainlit chat"
            style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
          />
        </Splitter.Panel>

        <Splitter.Panel min="20%">
          <div style={{ position: 'relative', width: '100%', height: '100%' }}>
            <iframe
              key={iframeKey}
              ref={previewRef}
              src="/preview/"
              onLoad={onPreviewLoad}
              title="Live preview"
              style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
            />
            {!previewReady && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 12,
                background: 'rgba(0,0,0,0.85)', color: '#e0e0e0', fontSize: 14,
              }}>
                <Spin size="large" />
                <div>Workspace booting — installing dependencies…</div>
                <div style={{ fontSize: 12, opacity: 0.6 }}>{bootElapsed}s elapsed</div>
                {bootElapsed > 60 && (
                  <div style={{ fontSize: 12, color: '#faad14' }}>
                    Still booting — check <code>docker compose logs workspace</code>
                  </div>
                )}
              </div>
            )}
          </div>
        </Splitter.Panel>
      </Splitter>
    </div>
  )
}
