export type Project = {
  id: string;
  name: string;
  bootstrap_url: string;
  target_url: string | null;
  created_at: string;
  last_opened_at: string | null;
  status: 'active' | 'archived';
};

export type Conversation = {
  id: string;
  project_id: string;
  title: string;
  status: 'active' | 'archived';
  engine_session: string | null;
  created_at: string;
  updated_at: string;
};

export type GitStatus =
  | { ok: false; reason: string }
  | {
      ok: true;
      branch: string;
      ahead: string | null;
      no_upstream: boolean;
      dirty_files: number;
      on_main: boolean;
    };

export type PublishResult =
  | { ok: true; branch: string; message: string; output: string }
  | { ok: false; step: 'branch' | 'commit' | 'push'; branch?: string; error: string };

export type SelectionPayload = {
  source?: string;
  component?: string;
  selector?: string;
  text?: string;
  html?: string;
  summary: string;
};

export type AgentStep = {
  type: 'agent_step';
  tool: 'text' | 'read' | 'edit' | 'write' | 'bash' | 'todowrite';
  label: string;
  input?: Record<string, unknown>;
  output?: string;
  status: 'completed' | 'streaming' | 'failed';
  part_id?: string;
};

export type AgentQuestion = {
  type: 'agent_question';
  question: string;
  header?: string;
  options: { label: string }[];
};

export type AgentResponse = {
  type: 'agent_response';
  text: string;
  files: string[];
};

export type AgentEvent = AgentStep | AgentQuestion | AgentResponse;

export type ModelProvider = 'openrouter' | 'local' | 'custom';

export type SettingsRead = {
  has_github_token: boolean;
  model_provider: ModelProvider | null;
  model_base_url: string | null;
  model_id: string | null;
  has_model_api_key: boolean;
  is_configured: boolean;
};

export type SettingsUpdate = {
  github_token?: string;
  model_api_key?: string;
  model_provider?: ModelProvider;
  model_base_url?: string;
  model_id?: string;
};

export type ModelInfo = { id: string; name: string };

export type ModelListResult = { models: ModelInfo[]; error?: string };

export type WorkspaceActive = { project_id: string | null; name: string | null };

export type SwitchSuccess = { ok: true; active_project_id: string };
export type SwitchNeedsConfirm = {
  ok: false;
  needs_confirm: true;
  dirty_files: number;
  current_project_id: string;
};
