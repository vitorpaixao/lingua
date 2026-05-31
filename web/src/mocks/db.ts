import type { Project } from '@/types/api';

const STORAGE_KEY = 'lingua_mock_projects';
const ACTIVE_KEY = 'lingua_mock_active_workspace';

function load(): Project[] {
  if (typeof window === 'undefined') return seed();
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const projects = seed();
    save(projects);
    return projects;
  }
  try {
    return JSON.parse(raw) as Project[];
  } catch {
    return seed();
  }
}

function save(projects: Project[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
}

function seed(): Project[] {
  const now = new Date().toISOString();
  return [
    {
      id: 'demo-counter',
      name: 'Counter Demo',
      bootstrap_url: 'https://github.com/example/vite-react-counter',
      target_url: 'https://github.com/example/counter-output',
      created_at: now,
      last_opened_at: now,
      status: 'active',
    },
    {
      id: 'demo-todo',
      name: 'Todo Sample',
      bootstrap_url: 'https://github.com/example/vite-react-todo',
      target_url: null,
      created_at: now,
      last_opened_at: null,
      status: 'active',
    },
  ];
}

export const mockDb = {
  list(includeArchived = false): Project[] {
    const all = load();
    return includeArchived ? all : all.filter((p) => p.status === 'active');
  },
  get(id: string): Project | undefined {
    return load().find((p) => p.id === id);
  },
  create(input: { name: string; bootstrap_url: string; target_url?: string }): Project {
    const now = new Date().toISOString();
    const proj: Project = {
      id: crypto.randomUUID(),
      name: input.name,
      bootstrap_url: input.bootstrap_url,
      target_url: input.target_url ?? null,
      created_at: now,
      last_opened_at: null,
      status: 'active',
    };
    save([...load(), proj]);
    return proj;
  },
  update(id: string, patch: Partial<Project>): Project | undefined {
    const all = load();
    const idx = all.findIndex((p) => p.id === id);
    if (idx < 0) return;
    all[idx] = { ...all[idx], ...patch };
    save(all);
    return all[idx];
  },
  archive(id: string): Project | undefined {
    return mockDb.update(id, { status: 'archived' });
  },
  getActive(): string | null {
    if (typeof window === 'undefined') return null;
    return window.localStorage.getItem(ACTIVE_KEY);
  },
  setActive(id: string | null) {
    if (typeof window === 'undefined') return;
    if (id) window.localStorage.setItem(ACTIVE_KEY, id);
    else window.localStorage.removeItem(ACTIVE_KEY);
  },
};
