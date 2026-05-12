const BASE = `http://${window.location.hostname}:8000`

export interface Project {
  id: string
  name: string
  bootstrap_url: string
  target_url: string | null
  created_at: string
  last_opened_at: string | null
  status: string
}

export interface GitStatus {
  ok: boolean
  branch?: string
  ahead?: string | null
  no_upstream?: boolean
  dirty_files?: number
  on_main?: boolean
  reason?: string
}

export interface GitPublishResult {
  ok: boolean
  branch?: string
  message?: string
  error?: string
  step?: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  listProjects: () => request<Project[]>('/api/projects'),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  createProject: (body: { name: string; bootstrap_url: string; target_url?: string }) =>
    request<Project>('/api/projects', { method: 'POST', body: JSON.stringify(body) }),
  touchProject: (id: string) =>
    request<Project>(`/api/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ last_opened_at: new Date().toISOString() }),
    }),
  gitStatus: () => request<GitStatus>('/api/git/status'),
  gitPublish: () => request<GitPublishResult>('/api/git/publish', { method: 'POST' }),
}
