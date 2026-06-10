import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
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
import { UserOutlined, RobotOutlined } from '@ant-design/icons';
import type { AgentEvent, AgentQuestion, SelectionPayload } from '@/types/api';
import { postChat, postAnswer } from '@/api/client';
import { SSEConnection } from '@/lib/sseClient';
import { getSessionId } from '@/lib/sessionId';

const { Text } = Typography;

type StepRow = {
  id: string;
  tool: string;
  label: string;
  input?: Record<string, unknown>;
  output?: string;
  status: 'completed' | 'streaming';
};

type BuildingState = {
  status: 'building' | 'needs-input' | 'done' | 'error';
  steps: StepRow[];
  thinking: string;
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

export function ChatPanel({
  selections,
  onRemoveSelection,
  onClearSelections,
}: {
  selections: SelectionPayload[];
  onRemoveSelection: (index: number) => void;
  onClearSelections: () => void;
}) {
  const { message: toast } = AntdApp.useApp();
  const { token } = theme.useToken();
  const sessionId = useMemo(() => getSessionId(), []);
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
      if (ev.type === 'agent_step') {
        if (ev.tool === 'text') {
          updateBuilding((s) => ({ ...s, thinking: ev.output ?? '' }));
        } else {
          updateBuilding((s) => ({
            ...s,
            steps: [
              ...s.steps,
              {
                id: `${Date.now()}-${Math.random()}`,
                tool: ev.tool,
                label: ev.label,
                input: ev.input,
                output: ev.output,
                status: 'completed',
              },
            ],
          }));
        }
      } else if (ev.type === 'agent_question') {
        setPendingQuestion(true);
        updateBuilding((s) => ({ ...s, status: 'needs-input', question: ev }));
      } else if (ev.type === 'agent_response') {
        setPendingQuestion(false);
        updateBuilding((s) => ({
          ...s,
          status: 'done',
          finalText: ev.text,
          files: ev.files,
        }));
        activeBuildingId.current = null;
      }
    },
    [updateBuilding],
  );

  useEffect(() => {
    const conn = new SSEConnection(`/api/chat/stream?session_id=${sessionId}`, {
      onEvent,
    });
    void conn.connect();
    return () => conn.close();
  }, [sessionId, onEvent]);

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
    setMessages((prev) => [
      ...prev,
      { kind: 'user', id: userId, text },
      {
        kind: 'building',
        id: buildingId,
        state: { status: 'building', steps: [], thinking: '' },
      },
    ]);
    setInput('');
    try {
      const res = await postChat({
        session_id: sessionId,
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
  }, [input, pendingQuestion, sessionId, selections, onClearSelections, toast, updateBuilding]);

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
        await postAnswer({ session_id: sessionId, answer });
      } catch (err) {
        toast.error(`Failed: ${(err as Error).message}`);
      }
    },
    [pendingQuestion, sessionId, toast, updateBuilding],
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
          borderTop: `1px solid ${token.colorBorderSecondary}`,
          background: token.colorBgContainer,
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
  const active = state.status === 'building' || state.status === 'needs-input';

  return (
    <Flex vertical gap={8} style={{ width: '100%' }}>
      {(state.thinking || state.steps.length > 0) && (
        <Think
          title={active ? 'Thinking…' : 'Thought'}
          loading={state.status === 'building'}
          defaultExpanded={active}
        >
          <Flex vertical gap={8} style={{ width: '100%' }}>
            {state.thinking && <Text>{state.thinking}</Text>}
            {state.steps.length > 0 && (
              <ThoughtChain
                items={state.steps.map((s) => ({
                  key: s.id,
                  title: s.label,
                  status: s.status === 'streaming' ? 'loading' : 'success',
                  collapsible: Boolean(s.output),
                  content: s.output ? (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {s.output}
                    </Text>
                  ) : undefined,
                }))}
              />
            )}
          </Flex>
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
