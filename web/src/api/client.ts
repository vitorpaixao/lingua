import type {
  Project,
  Conversation,
  GitStatus,
  PublishResult,
  ModelListResult,
  ModelProvider,
  SelectionPayload,
  SettingsRead,
  SettingsUpdate,
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
  conversation_id: string;
  prompt: string;
  selections?: SelectionPayload[];
};

export function postChat(body: ChatBody) {
  return request<{ ok: true } | { ok: false; reason: string }>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function postAnswer(body: { conversation_id: string; answer: string }) {
  return request<{ ok: boolean }>('/api/chat/answer', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

// ----- Conversations -----

export const listConversations = (projectId: string, includeArchived = false) =>
  request<Conversation[]>(
    `/api/projects/${projectId}/conversations${
      includeArchived ? '?include_archived=true' : ''
    }`,
  );

export const createConversation = (projectId: string, title?: string) =>
  request<Conversation>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, title }),
  });

export const getConversation = (id: string) =>
  request<Conversation>(`/api/conversations/${id}`);

export const renameConversation = (id: string, title: string) =>
  request<Conversation>(`/api/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  });

export const archiveConversation = (id: string) =>
  request<Conversation>(`/api/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'archived' }),
  });

export const deleteConversation = (id: string) =>
  request<{ ok: boolean }>(`/api/conversations/${id}`, { method: 'DELETE' });

export const getConversationEvents = (id: string) =>
  request<Record<string, unknown>[]>(`/api/conversations/${id}/events`);

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
  create_github_repo?: boolean;
  visibility?: 'private' | 'public';
  description?: string;
}) => request<Project>('/api/projects', { method: 'POST', body: JSON.stringify(body) });

// ----- Settings (credential vault) -----

export const getSettings = () => request<SettingsRead>('/api/settings');

export const updateSettings = (patch: SettingsUpdate) =>
  request<SettingsRead>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(patch),
  });

export const listModels = (body: {
  provider: ModelProvider;
  base_url?: string;
  api_key?: string;
}) =>
  request<ModelListResult>('/api/models/list', {
    method: 'POST',
    body: JSON.stringify(body),
  });

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
