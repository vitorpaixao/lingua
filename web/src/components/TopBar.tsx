import { useEffect, useState } from 'react'
import { api, type GitStatus } from '../api/client'

interface TopBarProps {
  onBack: () => void
  pickMode: boolean
  onTogglePick: () => void
  copyToast: string | null
}

export function TopBar({ onBack, pickMode, onTogglePick, copyToast }: TopBarProps) {
  const [status, setStatus] = useState<GitStatus | null>(null)
  const [publishing, setPublishing] = useState(false)
  const [publishMsg, setPublishMsg] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      try {
        const s = await api.gitStatus()
        if (!cancelled) setStatus(s)
      } catch {}
    }
    poll()
    const id = setInterval(poll, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  const publish = async () => {
    setPublishing(true)
    setPublishMsg(null)
    try {
      const r = await api.gitPublish()
      setPublishMsg(r.ok ? `Pushed: ${r.branch}` : `Error: ${r.error ?? r.step}`)
    } catch (e) {
      setPublishMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setPublishing(false)
    }
  }

  const branchLabel = status?.ok
    ? `⎇ ${status.branch}${status.ahead ? ` · ${status.ahead} ahead` : ''}${status.no_upstream ? ' · no upstream' : ''}`
    : '⎇ —'

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-gray-900 text-white text-sm border-b border-gray-700">
      <span className="font-mono text-gray-300">{branchLabel}</span>
      {status?.dirty_files ? (
        <span className="text-yellow-400 text-xs">{status.dirty_files} unsaved</span>
      ) : null}
      <div className="flex-1" />
      {copyToast && (
        <span className="text-xs text-green-400">{copyToast} ✓ paste into chat</span>
      )}
      {publishMsg && (
        <span className={`text-xs ${publishMsg.startsWith('Error') ? 'text-red-400' : 'text-green-400'}`}>
          {publishMsg}
        </span>
      )}
      <button
        onClick={onTogglePick}
        className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
          pickMode
            ? 'bg-blue-500 hover:bg-blue-400 text-white'
            : 'bg-gray-700 hover:bg-gray-600 text-white'
        }`}
      >
        {pickMode ? 'Picking… (ESC)' : 'Select'}
      </button>
      <button
        onClick={publish}
        disabled={publishing}
        className="px-3 py-1 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 rounded text-sm font-medium transition-colors"
      >
        {publishing ? 'Publishing…' : 'Publish'}
      </button>
      <button
        onClick={onBack}
        className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
      >
        ← Back
      </button>
    </div>
  )
}
