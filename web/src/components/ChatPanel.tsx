import { useEffect, useRef, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import { Bubble, Sender, Think, ThoughtChain } from '@ant-design/x';
import {
  Avatar,
  Button,
  Card,
  Flex,
  Input,
  Space,
  Tag,
  Typography,
  App as AntdApp,
  theme,
} from 'antd';
import {
  UserOutlined,
  RobotOutlined,
  AimOutlined,
  BulbOutlined,
  FileSearchOutlined,
  EditOutlined,
  FileAddOutlined,
  CodeOutlined,
  ScheduleOutlined,
  ToolOutlined,
  LoadingOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import type { AgentEvent, AgentQuestion, SelectionPayload } from '@/types/api';
import { postChat, postAnswer, getConversationEvents } from '@/api/client';
import { SSEConnection } from '@/lib/sseClient';

const { Text } = Typography;

type ProcessEntry =
  | { kind: 'text'; id: string; text: string }
  | { kind: 'selection'; id: string; selections: SelectionPayload[] }
  | {
      kind: 'tool';
      id: string;
      tool: string;
      label: string;
      output?: string;
      status: 'completed' | 'streaming' | 'failed';
    };

type BuildingState = {
  status: 'building' | 'needs-input' | 'done' | 'error';
  entries: ProcessEntry[];
  question?: AgentQuestion;
  finalText?: string;
  files?: string[];
};

type ChatMessage =
  | { kind: 'user'; id: string; text: string }
  | { kind: 'building'; id: string; state: BuildingState };

function roleFor(m: ChatMessage): 'user' | 'agent' {
  return m.kind === 'user' ? 'user' : 'agent';
}

/** Pure reducer: fold one agent event into a building message's state. Shared by the
 *  live SSE handler and the transcript replay so both render identically. */
function applyAgentEvent(s: BuildingState, ev: AgentEvent): BuildingState {
  if (ev.type === 'agent_step') {
    if (ev.tool === 'text') {
      const partId = ev.part_id ?? 'text';
      const text = ev.output ?? '';
      const idx = s.entries.findIndex((e) => e.kind === 'text' && e.id === partId);
      if (idx >= 0) {
        const entries = [...s.entries];
        entries[idx] = { kind: 'text', id: partId, text };
        return { ...s, entries };
      }
      return { ...s, entries: [...s.entries, { kind: 'text', id: partId, text }] };
    }
    return {
      ...s,
      entries: [
        ...s.entries,
        {
          kind: 'tool',
          id: `${Date.now()}-${Math.random()}`,
          tool: ev.tool,
          label: ev.label,
          output: ev.output,
          status: ev.status,
        },
      ],
    };
  }
  if (ev.type === 'agent_question') {
    return { ...s, status: 'needs-input', question: ev };
  }
  if (ev.type === 'agent_response') {
    // Drop the trailing text entry equal to the final answer (shown in the result area).
    const entries = [...s.entries];
    for (let i = entries.length - 1; i >= 0; i--) {
      const e = entries[i];
      if (e.kind === 'text') {
        if (e.text === ev.text) entries.splice(i, 1);
        break;
      }
    }
    return { ...s, status: 'done', finalText: ev.text, files: ev.files, entries };
  }
  return s;
}

type ReplayEvent =
  | AgentEvent
  | { type: 'user'; text: string; selections?: SelectionPayload[] | null };

/** Rebuild the message list from a Conversation's durable event transcript. */
function buildMessagesFromEvents(events: ReplayEvent[]): {
  messages: ChatMessage[];
  pendingQuestion: boolean;
} {
  const messages: ChatMessage[] = [];
  let building: BuildingState | null = null;
  let buildingId = '';
  let i = 0;
  const flush = () => {
    if (building) {
      messages.push({ kind: 'building', id: buildingId, state: building });
      building = null;
    }
  };
  for (const ev of events) {
    if (ev.type === 'user') {
      flush();
      messages.push({ kind: 'user', id: `ru-${i}`, text: ev.text });
      buildingId = `rb-${i}`;
      const sels = ev.selections ?? [];
      building = {
        status: 'done', // a turn with no response stays collapsed, not spinning
        entries:
          sels.length > 0
            ? [{ kind: 'selection', id: `rsel-${i}`, selections: sels }]
            : [],
      };
    } else {
      if (!building) {
        buildingId = `rb-${i}`;
        building = { status: 'done', entries: [] };
      }
      building = applyAgentEvent(building, ev as AgentEvent);
    }
    i++;
  }
  flush();
  const last = messages[messages.length - 1];
  const pendingQuestion =
    !!last && last.kind === 'building' && last.state.status === 'needs-input';
  return { messages, pendingQuestion };
}

export function ChatPanel({
  conversationId,
  selections,
  onRemoveSelection,
  onClearSelections,
}: {
  conversationId: string;
  selections: SelectionPayload[];
  onRemoveSelection: (index: number) => void;
  onClearSelections: () => void;
}) {
  const { message: toast } = AntdApp.useApp();
  const { token } = theme.useToken();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState(false);
  const [openTextAnswer] = useState(false);
  const [textAnswer, setTextAnswer] = useState('');
  const activeBuildingId = useRef<string | null>(null);

  const updateBuilding = useCallback((patch: (s: BuildingState) => BuildingState) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.kind === 'building' && m.id === activeBuildingId.current
          ? { ...m, state: patch(m.state) }
          : m,
      ),
    );
  }, []);

  const onEvent = useCallback(
    (ev: AgentEvent) => {
      if (ev.type === 'agent_question') setPendingQuestion(true);
      if (ev.type === 'agent_response') setPendingQuestion(false);
      updateBuilding((s) => applyAgentEvent(s, ev));
      if (ev.type === 'agent_response') activeBuildingId.current = null;
    },
    [updateBuilding],
  );

  // Load the durable transcript, then stream live events — re-runs per conversation.
  useEffect(() => {
    let cancelled = false;
    activeBuildingId.current = null;
    setMessages([]);
    setPendingQuestion(false);
    (async () => {
      try {
        const events = await getConversationEvents(conversationId);
        if (cancelled) return;
        const { messages: replayed, pendingQuestion: pq } = buildMessagesFromEvents(
          events as unknown as Parameters<typeof buildMessagesFromEvents>[0],
        );
        setMessages(replayed);
        setPendingQuestion(pq);
      } catch {
        // new/unknown conversation — start empty
      }
    })();
    const conn = new SSEConnection(
      `/api/chat/stream?conversation_id=${conversationId}`,
      { onEvent },
    );
    void conn.connect();
    return () => {
      cancelled = true;
      conn.close();
    };
  }, [conversationId, onEvent]);

  const sendPrompt = useCallback(async () => {
    const text = input.trim();
    if (!text) return;
    if (pendingQuestion) {
      toast.warning('Answer the pending question first');
      return;
    }
    const userId = `u-${Date.now()}`;
    const buildingId = `b-${Date.now()}`;
    activeBuildingId.current = buildingId;
    const snapshot = selections;
    const initialEntries: ProcessEntry[] =
      snapshot.length > 0
        ? [{ kind: 'selection', id: `sel-${buildingId}`, selections: snapshot }]
        : [];
    setMessages((prev) => [
      ...prev,
      { kind: 'user', id: userId, text },
      {
        kind: 'building',
        id: buildingId,
        state: { status: 'building', entries: initialEntries },
      },
    ]);
    setInput('');
    try {
      const res = await postChat({
        conversation_id: conversationId,
        prompt: text,
        selections: snapshot.length > 0 ? snapshot : undefined,
      });
      if (!('ok' in res) || res.ok === false) {
        toast.error('Server rejected the prompt');
        updateBuilding((s) => ({ ...s, status: 'error' }));
        return;
      }
      if (snapshot.length > 0) onClearSelections();
    } catch (err) {
      toast.error(`Failed: ${(err as Error).message}`);
      updateBuilding((s) => ({ ...s, status: 'error' }));
    }
  }, [input, pendingQuestion, conversationId, selections, onClearSelections, toast, updateBuilding]);

  const sendAnswer = useCallback(
    async (answer: string) => {
      if (!pendingQuestion) return;
      setPendingQuestion(false);
      setTextAnswer('');
      setMessages((prev) => [
        ...prev,
        { kind: 'user', id: `u-${Date.now()}`, text: `You chose: ${answer}` },
      ]);
      updateBuilding((s) => ({ ...s, status: 'building', question: undefined }));
      try {
        await postAnswer({ conversation_id: conversationId, answer });
      } catch (err) {
        toast.error(`Failed: ${(err as Error).message}`);
      }
    },
    [pendingQuestion, conversationId, toast, updateBuilding],
  );

  const bubbleItems = messages.map((m) => ({
    key: m.id,
    role: roleFor(m),
    content: renderContent(m, sendAnswer),
  }));

  return (
    <Flex vertical style={{ height: '100%', minWidth: 0 }}>
      <Flex
        vertical
        flex={1}
        style={{ overflow: 'auto', padding: 16, background: token.colorBgLayout }}
      >
        <Bubble.List
          autoScroll
          role={{
            user: {
              placement: 'end',
              avatar: <Avatar icon={<UserOutlined />} />,
            },
            agent: {
              placement: 'start',
              avatar: <Avatar icon={<RobotOutlined />} />,
            },
          }}
          items={bubbleItems}
        />
      </Flex>
      <Flex
        style={{
          padding: 12,
          background: token.colorBgLayout,
        }}
      >
        {pendingQuestion && openTextAnswer ? (
          <Input.Search
            value={textAnswer}
            onChange={(e) => setTextAnswer(e.target.value)}
            placeholder="Type your answer…"
            enterButton="Send"
            onSearch={(v) => sendAnswer(v)}
          />
        ) : (
          <Sender
            header={
              <Sender.Header
                title={`Selected (${selections.length})`}
                open={selections.length > 0}
                onOpenChange={(open) => {
                  if (!open) onClearSelections();
                }}
                closable
              >
                <Flex wrap gap={8}>
                  {selections.map((s, i) => (
                    <Tag
                      key={`${s.summary}-${i}`}
                      closable
                      onClose={(e) => {
                        e.preventDefault();
                        onRemoveSelection(i);
                      }}
                      color="blue"
                    >
                      {s.summary}
                      {s.source ? (
                        <Text type="secondary" style={{ marginLeft: 4 }}>
                          · {s.source}
                        </Text>
                      ) : null}
                    </Tag>
                  ))}
                </Flex>
              </Sender.Header>
            }
            value={input}
            onChange={setInput}
            onSubmit={sendPrompt}
            placeholder={
              pendingQuestion ? 'Answer the question above first' : 'Tell me what to build…'
            }
            disabled={pendingQuestion}
          />
        )}
      </Flex>
    </Flex>
  );
}

function renderContent(m: ChatMessage, sendAnswer: (a: string) => void) {
  if (m.kind === 'user') {
    return m.text;
  }
  return <BuildingBubble state={m.state} onAnswer={sendAnswer} />;
}

function BuildingBubble({
  state,
  onAnswer,
}: {
  state: BuildingState;
  onAnswer: (a: string) => void;
}) {
  const { token } = theme.useToken();
  const active = state.status === 'building' || state.status === 'needs-input';

  const [expanded, setExpanded] = useState(true);
  useEffect(() => {
    if (state.status === 'done' || state.status === 'error') setExpanded(false);
  }, [state.status]);

  const entryIcon = (e: ProcessEntry): ReactNode => {
    if (e.kind === 'tool') {
      if (e.status === 'streaming')
        return <LoadingOutlined style={{ color: token.colorPrimary }} />;
      if (e.status === 'failed')
        return <CloseCircleOutlined style={{ color: token.colorError }} />;
    }
    const color =
      e.kind === 'selection'
        ? token.colorWarning
        : e.kind === 'text'
        ? token.colorPrimary
        : token.colorSuccess; // completed tool
    const style = { color };
    switch (e.kind === 'tool' ? e.tool : e.kind) {
      case 'selection':
        return <AimOutlined style={style} />;
      case 'text':
        return <BulbOutlined style={style} />;
      case 'read':
        return <FileSearchOutlined style={style} />;
      case 'edit':
        return <EditOutlined style={style} />;
      case 'write':
        return <FileAddOutlined style={style} />;
      case 'bash':
        return <CodeOutlined style={style} />;
      case 'todowrite':
        return <ScheduleOutlined style={style} />;
      default:
        return <ToolOutlined style={style} />;
    }
  };

  return (
    <Flex vertical gap={8} style={{ width: '100%' }}>
      {state.entries.length > 0 && (
        <Think
          title={active ? 'Thinking…' : 'Thought'}
          loading={state.status === 'building'}
          expanded={expanded}
          onExpand={setExpanded}
        >
          <ThoughtChain
            items={state.entries.map((e) =>
              e.kind === 'selection'
                ? {
                    key: e.id,
                    title: 'Selected from preview',
                    icon: entryIcon(e),
                    collapsible: true,
                    content: (
                      <Flex vertical gap={6}>
                        {e.selections.map((sel, i) => (
                          <Flex key={`${sel.summary}-${i}`} vertical gap={2}>
                            <Text strong>{sel.summary}</Text>
                            {sel.component && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                component: {sel.component}
                              </Text>
                            )}
                            {sel.selector && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                selector: {sel.selector}
                              </Text>
                            )}
                            {sel.source && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                source: {sel.source}
                              </Text>
                            )}
                            {sel.text && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                “{sel.text.slice(0, 120)}
                                {sel.text.length > 120 ? '…' : ''}”
                              </Text>
                            )}
                          </Flex>
                        ))}
                      </Flex>
                    ),
                  }
                : e.kind === 'text'
                ? {
                    key: e.id,
                    title: 'Reasoning',
                    icon: entryIcon(e),
                    collapsible: true,
                    content: <Text>{e.text}</Text>,
                  }
                : {
                    key: e.id,
                    title: e.label,
                    icon: entryIcon(e),
                    collapsible: Boolean(e.output),
                    content: e.output ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {e.output}
                      </Text>
                    ) : undefined,
                  },
            )}
          />
        </Think>
      )}
      {state.question && (
        <Card size="small">
          {state.question.header && (
            <>
              <Text strong>{state.question.header}</Text>
              <br />
            </>
          )}
          <Text>{state.question.question}</Text>
          <br />
          <Space wrap style={{ marginTop: 8 }}>
            {state.question.options.length > 0 ? (
              state.question.options.map((opt) => (
                <Button key={opt.label} type="default" onClick={() => onAnswer(opt.label)}>
                  {opt.label}
                </Button>
              ))
            ) : (
              <Button type="default" onClick={() => onAnswer('continue')}>
                Continue
              </Button>
            )}
          </Space>
        </Card>
      )}
      {state.status === 'done' && (
        <Flex vertical gap={4}>
          {state.finalText && <Text>{state.finalText}</Text>}
          {state.files?.length ? (
            <Space wrap size={4}>
              {state.files.map((f) => (
                <Tag key={f}>{f}</Tag>
              ))}
            </Space>
          ) : null}
        </Flex>
      )}
      {state.status === 'error' && <Text type="danger">Something went wrong.</Text>}
    </Flex>
  );
}
