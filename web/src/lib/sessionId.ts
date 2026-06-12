const STORAGE_KEY = 'lingua_session_id';

export function getSessionId(): string {
  if (typeof window === 'undefined' || !window.localStorage) {
    return crypto.randomUUID();
  }
  let id = window.localStorage.getItem(STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}

export function resetSessionId(): string {
  const id = crypto.randomUUID();
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.setItem(STORAGE_KEY, id);
  }
  return id;
}
