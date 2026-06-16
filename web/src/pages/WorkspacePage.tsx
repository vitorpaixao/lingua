import { useEffect, useRef, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Flex, Spin, Splitter, theme } from 'antd';
import { WorkspaceHeader } from '@/components/WorkspaceHeader';
import { PreviewToolbar } from '@/components/PreviewToolbar';
import { ChatPanel } from '@/components/ChatPanel';
import { ActivityTabs } from '@/components/ActivityTabs';
import { ConversationSelect } from '@/components/ConversationSelect';
import { ConversationList } from '@/components/ConversationList';
import { PreviewPanel } from '@/components/PreviewPanel';
import {
  getProject,
  getActiveWorkspace,
  switchWorkspace,
  listConversations,
  createConversation,
} from '@/api/client';
import type { Project, SelectionPayload } from '@/types/api';

const DRAG_KEY = 'lingua_preview_width';

function loadPreviewPct(): number {
  const stored = Number(window.localStorage.getItem(DRAG_KEY));
  return stored >= 20 && stored <= 80 ? stored : 50;
}

export function WorkspacePage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const projectId = params.get('id');
  const conversationId = params.get('c');

  // The chat column shows either the active chat ('chat') or the conversation list ('list').
  const [view, setView] = useState<'chat' | 'list'>('chat');

  const selectConversation = useCallback(
    (id: string) => {
      if (projectId) nav(`/workspace?id=${projectId}&c=${id}`);
      setView('chat');
    },
    [projectId, nav],
  );

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [pickMode, setPickMode] = useState(false);
  const [selections, setSelections] = useState<SelectionPayload[]>([]);
  const [previewKey, setPreviewKey] = useState(0);
  const [convTitle, setConvTitle] = useState('Conversations');
  const { token } = theme.useToken();

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const previewPctRef = useRef<number>(loadPreviewPct());

  // Load + activate project
  useEffect(() => {
    if (!projectId) {
      nav('/');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const proj = await getProject(projectId);
        if (cancelled) return;
        setProject(proj);
        const active = await getActiveWorkspace();
        if (active.project_id !== proj.id) {
          await switchWorkspace(proj.id, true);
          // Force iframe to unmount + remount so Vite re-evaluates the new project
          setPreviewKey((k) => k + 1);
        }
      } catch {
        nav('/');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, nav]);

  // Ensure a conversation is selected: default to the most-recent, or create one.
  useEffect(() => {
    if (!projectId || conversationId) return;
    let cancelled = false;
    (async () => {
      try {
        const list = await listConversations(projectId);
        if (cancelled) return;
        const target = list[0] ?? (await createConversation(projectId));
        if (cancelled) return;
        nav(`/workspace?id=${projectId}&c=${target.id}`, { replace: true });
      } catch {
        // leave unselected; sidebar can create one
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, conversationId, nav]);

  // Resolve the active conversation's title for the selector label.
  useEffect(() => {
    if (!projectId || !conversationId) {
      setConvTitle('Conversations');
      return;
    }
    let cancelled = false;
    listConversations(projectId)
      .then((list) => {
        if (cancelled) return;
        setConvTitle(list.find((c) => c.id === conversationId)?.title ?? 'Conversations');
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectId, conversationId]);

  // postMessage listener for picker
  useEffect(() => {
    const handler = (e: MessageEvent) => {
      const data = e.data as { type?: string; payload?: SelectionPayload };
      if (!data || typeof data !== 'object') return;
      if (data.type === 'lingua:selection' && data.payload) {
        const picked = data.payload;
        setSelections((prev) => [...prev, picked]);
        setPickMode(false);
        iframeRef.current?.contentWindow?.postMessage({ type: 'lingua:disable' }, '*');
      } else if (data.type === 'lingua:cancel') {
        setPickMode(false);
      }
    };
    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && pickMode) {
        setPickMode(false);
        iframeRef.current?.contentWindow?.postMessage({ type: 'lingua:disable' }, '*');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pickMode]);

  const onTogglePick = useCallback(() => {
    setPickMode((prev) => {
      const next = !prev;
      iframeRef.current?.contentWindow?.postMessage(
        { type: next ? 'lingua:enable_pick' : 'lingua:disable' },
        '*',
      );
      return next;
    });
  }, []);

  const onPreviewLoad = useCallback(() => {
    try {
      const doc = iframeRef.current?.contentDocument;
      if (!doc) return;
      if (doc.getElementById('lingua-picker-script')) return;
      const s = doc.createElement('script');
      s.id = 'lingua-picker-script';
      s.src = '/lingua-picker.js';
      doc.head.appendChild(s);
    } catch {
      // cross-origin or not loaded yet
    }
  }, []);

  if (loading || !project) {
    return (
      <Flex justify="center" align="center" style={{ height: '100vh' }}>
        <Spin size="large" />
      </Flex>
    );
  }

  const initialPct = previewPctRef.current;

  return (
    <Flex vertical style={{ height: '100vh' }}>
      <Flex flex={1} style={{ minHeight: 0 }}>
        <Splitter
          style={{ flex: 1, minHeight: 0 }}
          onResizeEnd={(sizes) => {
            // sizes is an array of pixel sizes; convert the second panel to %
            const total = sizes[0] + sizes[1];
            if (total > 0) {
              const pct = Math.round((sizes[1] / total) * 100);
              previewPctRef.current = pct;
              window.localStorage.setItem(DRAG_KEY, String(pct));
            }
          }}
        >
          {/* Left column: header, horizontal activity tabs, conversation selector, chat */}
          <Splitter.Panel min="25%" defaultSize={`${100 - initialPct}%`}>
            <Flex
              vertical
              style={{ height: '100%', minWidth: 0, background: token.colorBgLayout }}
            >
              <WorkspaceHeader />
              <div style={{ padding: 8, flexShrink: 0 }}>
                <ActivityTabs />
              </div>
              <div style={{ padding: '0 8px 8px', flexShrink: 0 }}>
                <ConversationSelect
                  title={convTitle}
                  open={view === 'list'}
                  onToggle={() => setView((v) => (v === 'list' ? 'chat' : 'list'))}
                />
              </div>
              <Flex vertical flex={1} style={{ minHeight: 0, minWidth: 0 }}>
                {view === 'list' ? (
                  <ConversationList
                    projectId={project.id}
                    activeId={conversationId}
                    onSelect={selectConversation}
                  />
                ) : conversationId ? (
                  <ChatPanel
                    conversationId={conversationId}
                    selections={selections}
                    onRemoveSelection={(i) =>
                      setSelections((prev) => prev.filter((_, idx) => idx !== i))
                    }
                    onClearSelections={() => setSelections([])}
                  />
                ) : (
                  <Flex justify="center" align="center" style={{ height: '100%' }}>
                    <Spin />
                  </Flex>
                )}
              </Flex>
            </Flex>
          </Splitter.Panel>

          {/* Preview column: "popped up" window card with its own toolbar */}
          <Splitter.Panel
            min="20%"
            max="80%"
            defaultSize={`${initialPct}%`}
            collapsible={{ start: true }}
          >
            <div
              style={{
                height: '100%',
                padding: 12,
                background: token.colorBgLayout,
                boxSizing: 'border-box',
              }}
            >
              <Flex
                vertical
                style={{
                  height: '100%',
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: token.borderRadiusLG,
                  padding: 8,
                  background: token.colorBgContainer,
                  boxShadow: token.boxShadowSecondary,
                  overflow: 'hidden',
                }}
              >
                <PreviewToolbar
                  projectName={project.name}
                  pickMode={pickMode}
                  onTogglePick={onTogglePick}
                />
                <div
                  style={{
                    flex: 1,
                    minHeight: 0,
                    overflow: 'hidden',
                    borderRadius: token.borderRadius,
                  }}
                >
                  <PreviewPanel
                    ref={iframeRef}
                    onLoad={onPreviewLoad}
                    reloadKey={previewKey}
                  />
                </div>
              </Flex>
            </div>
          </Splitter.Panel>
        </Splitter>
      </Flex>
    </Flex>
  );
}
