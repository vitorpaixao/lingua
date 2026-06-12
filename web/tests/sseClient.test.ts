import { describe, it, expect, vi } from 'vitest';
import { SSEConnection } from '@/lib/sseClient';
import type { AgentEvent } from '@/types/api';

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c));
      controller.close();
    },
  });
}

describe('SSEConnection', () => {
  it('parses well-formed events and dispatches them', async () => {
    const events: AgentEvent[] = [];
    const fetchMock = vi.fn().mockResolvedValueOnce({
      ok: true,
      body: makeStream([
        'id: 1\ndata: {"type":"agent_step","tool":"text","label":"Thinking","output":"Hello","status":"streaming"}\n\n',
        'id: 2\ndata: {"type":"agent_response","text":"done","files":[]}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const conn = new SSEConnection('/api/chat/stream?session_id=x', {
      onEvent: (ev) => {
        events.push(ev);
        if (ev.type === 'agent_response') conn.close();
      },
    });
    await conn.connect();

    expect(events).toHaveLength(2);
    expect(events[0]).toMatchObject({ type: 'agent_step', tool: 'text' });
    expect(events[1]).toMatchObject({ type: 'agent_response', text: 'done' });
  });

  it('ignores keep-alive comments', async () => {
    const events: AgentEvent[] = [];
    const fetchMock = vi.fn().mockResolvedValueOnce({
      ok: true,
      body: makeStream([
        ': keep-alive\n\n',
        'data: {"type":"agent_response","text":"ok","files":[]}\n\n',
      ]),
    });
    vi.stubGlobal('fetch', fetchMock);

    const conn = new SSEConnection('/api/chat/stream', {
      onEvent: (ev) => {
        events.push(ev);
        if (ev.type === 'agent_response') conn.close();
      },
    });
    await conn.connect();

    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('agent_response');
  });

  it('sends Last-Event-ID on reconnect after error', async () => {
    let calls = 0;
    const fetchMock = vi.fn().mockImplementation(async (_url, init: RequestInit) => {
      calls += 1;
      if (calls === 1) {
        return {
          ok: true,
          body: makeStream([
            'id: 42\ndata: {"type":"agent_step","tool":"text","label":"Thinking","status":"streaming"}\n\n',
          ]),
        };
      }
      // On second call, verify header
      expect((init.headers as Record<string, string>)['Last-Event-ID']).toBe('42');
      return {
        ok: true,
        body: makeStream([
          'id: 43\ndata: {"type":"agent_response","text":"done","files":[]}\n\n',
        ]),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    const events: AgentEvent[] = [];
    const conn = new SSEConnection('/api/chat/stream', {
      onEvent: (ev) => {
        events.push(ev);
        if (ev.type === 'agent_response') conn.close();
      },
    });
    await conn.connect();

    expect(calls).toBeGreaterThanOrEqual(2);
    expect(events).toHaveLength(2);
  });
});
