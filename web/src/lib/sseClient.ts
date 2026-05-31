import type { AgentEvent } from '@/types/api';

/**
 * Connect to /api/chat/stream as an SSE consumer using fetch (so we can read
 * response headers and handle reconnect ourselves — EventSource doesn't expose
 * Last-Event-ID nicely in some environments).
 *
 * The browser's native EventSource is fine for production with same-origin SSE,
 * but using fetch-based streaming gives us identical behavior under MSW (which
 * does not implement EventSource semantics on its mocked stream).
 */
export type SSEHandlers = {
  onEvent: (ev: AgentEvent) => void;
  onError?: (err: unknown) => void;
  onOpen?: () => void;
};

export class SSEConnection {
  private controller: AbortController | null = null;
  private closed = false;
  private lastEventId: string | null = null;

  constructor(
    private readonly url: string,
    private readonly handlers: SSEHandlers,
  ) {}

  async connect(): Promise<void> {
    while (!this.closed) {
      this.controller = new AbortController();
      try {
        const headers: Record<string, string> = { Accept: 'text/event-stream' };
        if (this.lastEventId) headers['Last-Event-ID'] = this.lastEventId;
        const res = await fetch(this.url, {
          headers,
          signal: this.controller.signal,
        });
        if (!res.ok || !res.body) {
          throw new Error(`SSE failed: ${res.status}`);
        }
        this.handlers.onOpen?.();
        await this.readStream(res.body);
        if (this.closed) return;
      } catch (err) {
        if (this.closed) return;
        this.handlers.onError?.(err);
      }
      // Reconnect after 1s backoff
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  close() {
    this.closed = true;
    this.controller?.abort();
  }

  private async readStream(body: ReadableStream<Uint8Array>) {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (!this.closed) {
      const { value, done } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });

      let split: number;
      while ((split = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        this.parseBlock(block);
      }
    }
  }

  private parseBlock(block: string) {
    let id: string | null = null;
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue; // comment / heartbeat
      if (line.startsWith('id: ')) id = line.slice(4).trim();
      else if (line.startsWith('data: ')) {
        data += (data ? '\n' : '') + line.slice(6);
      }
    }
    if (!data) return;
    if (id) this.lastEventId = id;
    try {
      const ev = JSON.parse(data) as AgentEvent;
      this.handlers.onEvent(ev);
    } catch {
      // ignore malformed
    }
  }
}
