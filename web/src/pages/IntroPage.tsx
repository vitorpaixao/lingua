import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Project } from '../api/client'
import { ProjectCard } from '../components/ProjectCard'
import { NewProjectDialog } from '../components/NewProjectDialog'

export function IntroPage() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showDialog, setShowDialog] = useState(false)

  useEffect(() => {
    api.listProjects()
      .then(setProjects)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const openProject = async (id: string) => {
    await api.touchProject(id).catch(() => {})
    navigate(`/workspace?id=${id}`)
  }

  const onCreated = (id: string) => {
    navigate(`/workspace?id=${id}`)
  }

  return (
    <div className="min-h-full bg-gray-900 text-white flex flex-col">
      <div className="flex items-center justify-between px-8 py-5 border-b border-gray-800">
        <h1 className="text-2xl font-bold tracking-tight">Lingua</h1>
        {projects.length > 0 && (
          <button
            onClick={() => setShowDialog(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-colors"
          >
            + New project
          </button>
        )}
      </div>

      <div className="flex-1 flex items-start justify-center px-8 py-12">
        {loading ? (
          <div className="text-gray-500 text-sm">Loading…</div>
        ) : projects.length === 0 ? (
          <div className="flex flex-col items-center gap-4 mt-16">
            <div className="text-gray-400 text-lg">No projects yet</div>
            <button
              onClick={() => setShowDialog(true)}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-500 rounded-xl text-base font-medium transition-colors"
            >
              + New project
            </button>
          </div>
        ) : (
          <div className="w-full max-w-3xl grid grid-cols-1 sm:grid-cols-2 gap-4">
            {projects.map(p => (
              <ProjectCard key={p.id} project={p} onClick={() => openProject(p.id)} />
            ))}
          </div>
        )}
      </div>

      {showDialog && (
        <NewProjectDialog onClose={() => setShowDialog(false)} onCreated={onCreated} />
      )}
    </div>
  )
}
