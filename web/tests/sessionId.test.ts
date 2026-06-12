import { describe, it, expect } from 'vitest';
import { getSessionId, resetSessionId } from '@/lib/sessionId';

describe('sessionId', () => {
  it('generates and persists a UUID', () => {
    const id1 = getSessionId();
    const id2 = getSessionId();
    expect(id1).toBe(id2);
    expect(id1).toMatch(/^[0-9a-f-]{36}$/i);
  });

  it('reuses the value across "page loads" (same localStorage)', () => {
    const id = getSessionId();
    // simulate fresh module call
    const again = getSessionId();
    expect(again).toBe(id);
  });

  it('resetSessionId returns a new UUID and updates storage', () => {
    const original = getSessionId();
    const replaced = resetSessionId();
    expect(replaced).not.toBe(original);
    expect(getSessionId()).toBe(replaced);
  });
});
