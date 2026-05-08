import { useState } from 'react'
import { api } from '../api/client'

interface NewProjectDialogProps {
  onClose: () => void
  onCreated: (id: string) => void
}

export function NewProjectDialog({ onClose, onCreated }: NewProjectDialogProps) {
  const [name, setName] = useState('')
  const [bootstrapUrl, setBootstrapUrl] = useState('')
  const [targetUrl, setTargetUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !bootstrapUrl.trim()) return
    setLoading(true)
    setError(null)
    try {
      const p = await api.createProject({
        name: name.trim(),
        bootstrap_url: bootstrapUrl.trim(),
        target_url: targetUrl.trim() || undefined,
      })
      onCreated(p.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-xl p-6 w-full max-w-md shadow-xl border border-gray-600">
        <h2 className="text-lg font-semibold text-white mb-4">New project</h2>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Name *</span>
            <input
              autoFocus
              required
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="My app"
              className="rounded px-3 py-2 bg-gray-700 text-white border border-gray-600 focus:outline-none focus:border-blue-500 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Bootstrap repo URL *</span>
            <input
              required
              value={bootstrapUrl}
              onChange={e => setBootstrapUrl(e.target.value)}
              placeholder="https://github.com/org/lingua--bootstrap"
              className="rounded px-3 py-2 bg-gray-700 text-white border border-gray-600 focus:outline-none focus:border-blue-500 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Target repo URL (optional)</span>
            <input
              value={targetUrl}
              onChange={e => setTargetUrl(e.target.value)}
              placeholder="https://github.com/org/my-app"
              className="rounded px-3 py-2 bg-gray-700 text-white border border-gray-600 focus:outline-none focus:border-blue-500 text-sm"
            />
          </label>
          {error && <div className="text-red-400 text-xs">{error}</div>}
          <div className="flex gap-2 mt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm text-gray-300 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2 rounded bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-sm text-white font-medium transition-colors"
            >
              {loading ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
