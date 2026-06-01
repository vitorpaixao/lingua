import { useEffect, useRef, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Flex, Spin, Splitter } from 'antd';
import { TopBar } from '@/components/TopBar';
import { ChatPanel } from '@/components/ChatPanel';
import { PreviewPanel } from '@/components/PreviewPanel';
import { getProject, getActiveWorkspace, switchWorkspace } from '@/api/client';
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

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [pickMode, setPickMode] = useState(false);
  const [selections, setSelections] = useState<SelectionPayload[]>([]);
  const [previewKey, setPreviewKey] = useState(0);

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
      <TopBar
        projectName={project.name}
        pickMode={pickMode}
        onTogglePick={onTogglePick}
      />
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
        <Splitter.Panel min="20%" defaultSize={`${100 - initialPct}%`}>
          <ChatPanel
            selections={selections}
            onRemoveSelection={(i) =>
              setSelections((prev) => prev.filter((_, idx) => idx !== i))
            }
            onClearSelections={() => setSelections([])}
          />
        </Splitter.Panel>
        <Splitter.Panel
          min="20%"
          max="80%"
          defaultSize={`${initialPct}%`}
          collapsible={{ start: true }}
        >
          <PreviewPanel
            ref={iframeRef}
            onLoad={onPreviewLoad}
            reloadKey={previewKey}
          />
        </Splitter.Panel>
      </Splitter>
    </Flex>
  );
}
