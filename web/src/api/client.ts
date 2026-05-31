import type {
  Project,
  GitStatus,
  PublishResult,
  SelectionPayload,
  WorkspaceActive,
  SwitchSuccess,
  SwitchNeedsConfirm,
} from '@/types/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    // 409 for needs_confirm is expected — caller handles it
    if (res.status === 409 || res.status === 400) {
      return (await res.json()) as T;
    }
    throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return (await res.json()) as T;
}

// ----- Chat -----

export type ChatBody = {
  session_id: string;
  prompt: string;
  selection?: SelectionPayload;
};

export function postChat(body: ChatBody) {
  return request<{ ok: true } | { ok: false; reason: string }>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function postAnswer(body: { session_id: string; answer: string }) {
  return request<{ ok: boolean }>('/api/chat/answer', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ----- Git -----

export const gitStatus = () => request<GitStatus>('/api/git/status');
export const gitPublish = () =>
  request<PublishResult>('/api/git/publish', { method: 'POST' });

// ----- Projects -----

export const listProjects = (includeArchived = false) =>
  request<Project[]>(
    `/api/projects${includeArchived ? '?include_archived=true' : ''}`,
  );

export const getProject = (id: string) => request<Project>(`/api/projects/${id}`);

export const createProject = (body: {
  name: string;
  bootstrap_url: string;
  target_url?: string;
}) => request<Project>('/api/projects', { method: 'POST', body: JSON.stringify(body) });

export const updateProject = (id: string, patch: Partial<Project>) =>
  request<Project>(`/api/projects/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });

export const archiveProject = (id: string) =>
  request<Project>(`/api/projects/${id}`, { method: 'DELETE' });

// ----- Workspace -----

export const getActiveWorkspace = () =>
  request<WorkspaceActive>('/api/workspace/active');

export const switchWorkspace = (project_id: string, force = false) =>
  request<SwitchSuccess | SwitchNeedsConfirm>('/api/workspace/switch', {
    method: 'POST',
    body: JSON.stringify({ project_id, force }),
  });
