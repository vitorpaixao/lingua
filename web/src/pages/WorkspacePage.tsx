import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type Project } from '../api/client'
import { TopBar } from '../components/TopBar'
import { Sidebar } from '../components/Sidebar'

export function WorkspacePage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const id = params.get('id') ?? ''
  const [project, setProject] = useState<Project | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pickMode, setPickMode] = useState(false)
  const [copyToast, setCopyToast] = useState<string | null>(null)
  const previewRef = useRef<HTMLIFrameElement | null>(null)

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

  if (error) {
    return (
      <div className="min-h-full bg-gray-900 flex items-center justify-center text-red-400">
        {error} — <button onClick={() => navigate('/')} className="ml-2 underline">back</button>
      </div>
    )
  }

  if (!project) {
    return (
      <div className="min-h-full bg-gray-900 flex items-center justify-center text-gray-500 text-sm">
        Loading…
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-gray-900">
      <TopBar
        onBack={() => navigate('/')}
        pickMode={pickMode}
        onTogglePick={() => setPickMode(v => !v)}
        copyToast={copyToast}
      />
      <div className="flex flex-1 min-h-0">
        <Sidebar project={project} />
        <iframe
          src={`http://${window.location.hostname}:8000`}
          title="Chainlit chat"
          className="w-[40%] flex-shrink-0 border-0"
        />
        <iframe
          ref={previewRef}
          src="/preview/"
          onLoad={onPreviewLoad}
          title="Live preview"
          className="w-[50%] flex-shrink-0 border-0 border-l border-gray-700"
        />
      </div>
    </div>
  )
}
