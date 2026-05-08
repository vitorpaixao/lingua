import { useEffect, useState } from 'react'
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

  useEffect(() => {
    if (!id) { navigate('/'); return }
    api.getProject(id)
      .then(setProject)
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
  }, [id, navigate])

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
      <TopBar onBack={() => navigate('/')} />
      <div className="flex flex-1 min-h-0">
        <Sidebar project={project} />
        <iframe
          src="http://localhost:8000"
          title="Chainlit chat"
          className="flex-1 border-0 min-w-0"
        />
        <iframe
          src="http://localhost:3000"
          title="Live preview"
          className="w-[480px] flex-shrink-0 border-0 border-l border-gray-700"
        />
      </div>
    </div>
  )
}
