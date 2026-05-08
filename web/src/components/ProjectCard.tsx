import { type Project } from '../api/client'

interface ProjectCardProps {
  project: Project
  onClick: () => void
}

export function ProjectCard({ project, onClick }: ProjectCardProps) {
  const opened = project.last_opened_at
    ? new Date(project.last_opened_at).toLocaleDateString()
    : null

  return (
    <button
      onClick={onClick}
      className="text-left p-4 rounded-lg border border-gray-700 bg-gray-800 hover:bg-gray-700 hover:border-gray-500 transition-colors w-full"
    >
      <div className="font-semibold text-white mb-1 truncate">{project.name}</div>
      {project.target_url && (
        <div className="text-xs text-gray-400 truncate mb-1">{project.target_url}</div>
      )}
      <div className="text-xs text-gray-500 truncate">{project.bootstrap_url}</div>
      {opened && <div className="text-xs text-gray-600 mt-2">Last opened {opened}</div>}
    </button>
  )
}
