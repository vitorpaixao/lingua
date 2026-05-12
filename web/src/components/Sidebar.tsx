import { type Project } from '../api/client'

interface SidebarProps {
  project: Project
}

export function Sidebar({ project }: SidebarProps) {
  return (
    <div className="w-[10%] flex-shrink-0 bg-gray-800 text-gray-200 flex flex-col p-4 gap-4 overflow-y-auto">
      <div>
        <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Project</div>
        <div className="font-semibold text-white truncate">{project.name}</div>
      </div>
      {project.target_url && (
        <div>
          <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Target repo</div>
          <a
            href={project.target_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-blue-400 hover:underline break-all"
          >
            {project.target_url}
          </a>
        </div>
      )}
      <div>
        <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Bootstrap</div>
        <a
          href={project.bootstrap_url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-400 hover:underline break-all"
        >
          {project.bootstrap_url}
        </a>
      </div>
      <div className="mt-auto text-xs text-yellow-400 bg-yellow-900/30 rounded p-2">
        Workspace volume not yet swapped per project — phase 2
      </div>
    </div>
  )
}
