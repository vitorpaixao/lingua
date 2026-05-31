import { http, HttpResponse } from 'msw';
import { mockDb } from './db';
import type { AgentEvent } from '@/types/api';

// ---------- chat ----------

const chatQueues = new Map<string, AgentEvent[]>();
const pendingQuestion = new Set<string>();

function queueForSession(sessionId: string): AgentEvent[] {
  let q = chatQueues.get(sessionId);
  if (!q) {
    q = [];
    chatQueues.set(sessionId, q);
  }
  return q;
}

function scriptedResponseFor(prompt: string): AgentEvent[] {
  // If prompt contains "?" → ask a clarifying question
  if (prompt.trim().endsWith('?')) {
    return [
      {
        type: 'agent_step',
        tool: 'text',
        label: 'Thinking',
        output: 'Hmm, I need a clarification before I can answer.',
        status: 'streaming',
      },
      {
        type: 'agent_question',
        question: 'Which area should I focus on?',
        header: 'Clarify',
        options: [{ label: 'UI' }, { label: 'Logic' }, { label: 'Tests' }],
      },
    ];
  }

  return [
    {
      type: 'agent_step',
      tool: 'text',
      label: 'Thinking',
      output: `Let me handle: "${prompt}". I'll read the current App.tsx first.`,
      status: 'streaming',
    },
    {
      type: 'agent_step',
      tool: 'read',
      label: 'Read `src/App.tsx`',
      input: { filePath: 'src/App.tsx' },
      output: '(file contents loaded)',
      status: 'completed',
    },
    {
      type: 'agent_step',
      tool: 'text',
      label: 'Thinking',
      output: `Let me handle: "${prompt}". I'll read the current App.tsx first. Now editing.`,
      status: 'streaming',
    },
    {
      type: 'agent_step',
      tool: 'edit',
      label: 'Edit `src/App.tsx`',
      input: { filePath: 'src/App.tsx', newString: '// mocked change' },
      output: 'Updated',
      status: 'completed',
    },
    {
      type: 'agent_response',
      text: `Done. I applied "${prompt}" to src/App.tsx.`,
      files: ['src/App.tsx'],
    },
  ];
}

function answerContinuation(): AgentEvent[] {
  return [
    {
      type: 'agent_step',
      tool: 'text',
      label: 'Thinking',
      output: 'Thanks. Continuing with your choice.',
      status: 'streaming',
    },
    {
      type: 'agent_step',
      tool: 'edit',
      label: 'Edit `src/App.tsx`',
      input: { filePath: 'src/App.tsx' },
      output: 'Updated',
      status: 'completed',
    },
    {
      type: 'agent_response',
      text: 'Done — change applied based on your answer.',
      files: ['src/App.tsx'],
    },
  ];
}

// ---------- handlers ----------

export const handlers = [
  // chat: submit prompt
  http.post('/api/chat', async ({ request }) => {
    const body = (await request.json()) as { session_id: string; prompt: string };
    if (pendingQuestion.has(body.session_id)) {
      return HttpResponse.json({ ok: false, reason: 'pending question' }, { status: 409 });
    }
    queueForSession(body.session_id).push(...scriptedResponseFor(body.prompt));
    return HttpResponse.json({ ok: true });
  }),

  // chat: SSE stream
  http.get('/api/chat/stream', ({ request }) => {
    const url = new URL(request.url);
    const sessionId = url.searchParams.get('session_id') ?? '';
    const queue = queueForSession(sessionId);
    let idCounter = 0;

    const stream = new ReadableStream<Uint8Array>({
      async start(controller) {
        const enc = new TextEncoder();
        const writeEvent = (ev: AgentEvent) => {
          idCounter += 1;
          const id = `${Date.now()}-${idCounter}`;
          controller.enqueue(enc.encode(`id: ${id}\ndata: ${JSON.stringify(ev)}\n\n`));
          if (ev.type === 'agent_question') pendingQuestion.add(sessionId);
          if (ev.type === 'agent_response') pendingQuestion.delete(sessionId);
        };

        // Drain whatever is in the queue, with small delays to simulate streaming
        let finished = false;
        while (!finished) {
          while (queue.length > 0) {
            const ev = queue.shift()!;
            writeEvent(ev);
            await new Promise((r) => setTimeout(r, 250));
            if (ev.type === 'agent_response') {
              finished = true;
              break;
            }
            if (ev.type === 'agent_question') {
              // Wait for the queue to grow via /api/chat/answer
              while (queue.length === 0) {
                await new Promise((r) => setTimeout(r, 200));
                controller.enqueue(enc.encode(`: keep-alive\n\n`));
              }
            }
          }
          if (!finished) {
            // No events yet — short poll
            await new Promise((r) => setTimeout(r, 200));
            controller.enqueue(enc.encode(`: keep-alive\n\n`));
          }
        }
        controller.close();
      },
    });

    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  }),

  // chat: answer
  http.post('/api/chat/answer', async ({ request }) => {
    const body = (await request.json()) as { session_id: string; answer: string };
    if (!pendingQuestion.has(body.session_id)) {
      return HttpResponse.json({ ok: false }, { status: 400 });
    }
    queueForSession(body.session_id).push(...answerContinuation());
    return HttpResponse.json({ ok: true });
  }),

  // git
  http.get('/api/git/status', () => {
    return HttpResponse.json({
      ok: true,
      branch: 'main',
      ahead: '0',
      no_upstream: false,
      dirty_files: 0,
      on_main: true,
    });
  }),
  http.post('/api/git/publish', () => {
    return HttpResponse.json({
      ok: true,
      branch: `lingua/${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, '')}`,
      message: 'Update from Lingua (mock)',
      output: 'Mock push succeeded',
    });
  }),

  // projects
  http.get('/api/projects', ({ request }) => {
    const url = new URL(request.url);
    const includeArchived = url.searchParams.get('include_archived') === 'true';
    return HttpResponse.json(mockDb.list(includeArchived));
  }),
  http.post('/api/projects', async ({ request }) => {
    const body = (await request.json()) as { name: string; bootstrap_url: string; target_url?: string };
    return HttpResponse.json(mockDb.create(body), { status: 201 });
  }),
  http.get('/api/projects/:id', ({ params }) => {
    const p = mockDb.get(params.id as string);
    return p ? HttpResponse.json(p) : new HttpResponse(null, { status: 404 });
  }),
  http.patch('/api/projects/:id', async ({ params, request }) => {
    const patch = (await request.json()) as Record<string, unknown>;
    const updated = mockDb.update(params.id as string, patch);
    return updated ? HttpResponse.json(updated) : new HttpResponse(null, { status: 404 });
  }),
  http.delete('/api/projects/:id', ({ params }) => {
    const archived = mockDb.archive(params.id as string);
    return archived ? HttpResponse.json(archived) : new HttpResponse(null, { status: 404 });
  }),

  // workspace
  http.get('/api/workspace/active', () => {
    const id = mockDb.getActive();
    if (!id) return HttpResponse.json({ project_id: null, name: null });
    const p = mockDb.get(id);
    return HttpResponse.json({ project_id: id, name: p?.name ?? null });
  }),
  http.post('/api/workspace/switch', async ({ request }) => {
    const body = (await request.json()) as { project_id: string; force?: boolean };
    const project = mockDb.get(body.project_id);
    if (!project) return new HttpResponse(null, { status: 404 });
    mockDb.setActive(body.project_id);
    mockDb.update(body.project_id, { last_opened_at: new Date().toISOString() });
    return HttpResponse.json({ ok: true, active_project_id: body.project_id });
  }),
];
