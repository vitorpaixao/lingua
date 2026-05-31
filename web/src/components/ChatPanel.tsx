import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { Bubble, Sender } from '@ant-design/x';
import {
  Avatar,
  Button,
  Card,
  Collapse,
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
  | { kind: 'building'; id: string; state: BuildingState }
  | { kind: 'agent-text'; id: string; text: string; files?: string[] };

function roleFor(m: ChatMessage): 'user' | 'agent' {
  return m.kind === 'user' ? 'user' : 'agent';
}

export function ChatPanel({
  selection,
  onConsumeSelection,
}: {
  selection: SelectionPayload | null;
  onConsumeSelection: () => void;
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
        const responseId = `r-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          { kind: 'agent-text', id: responseId, text: ev.text, files: ev.files },
        ]);
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
    const snapshot = selection;
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
        selection: snapshot ?? undefined,
      });
      if (!('ok' in res) || res.ok === false) {
        toast.error('Server rejected the prompt');
        updateBuilding((s) => ({ ...s, status: 'error' }));
        return;
      }
      if (snapshot) onConsumeSelection();
    } catch (err) {
      toast.error(`Failed: ${(err as Error).message}`);
      updateBuilding((s) => ({ ...s, status: 'error' }));
    }
  }, [input, pendingQuestion, sessionId, selection, onConsumeSelection, toast, updateBuilding]);

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
  if (m.kind === 'agent-text') {
    return (
      <Flex vertical gap={4} style={{ width: '100%' }}>
        <Text>{m.text}</Text>
        {m.files && m.files.length > 0 && (
          <Space wrap size={4}>
            {m.files.map((f) => (
              <Tag key={f}>{f}</Tag>
            ))}
          </Space>
        )}
      </Flex>
    );
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
  const header =
    state.status === 'needs-input'
      ? 'Needs input · Waiting for your answer'
      : state.status === 'done'
      ? `Done${state.files?.length ? ` · Changed: ${state.files.join(', ')}` : ''}`
      : state.status === 'error'
      ? 'Error'
      : `Building… (${state.steps.length} action${state.steps.length === 1 ? '' : 's'})`;

  const items = [
    {
      key: 'main',
      label: header,
      children: (
        <Flex vertical gap={6} style={{ width: '100%' }}>
          {state.thinking && (
            <Card size="small">
              <Text type="secondary" style={{ fontSize: 12 }}>Thinking</Text>
              <br />
              <Text>{state.thinking}</Text>
            </Card>
          )}
          {state.steps.map((s) => (
            <Card key={s.id} size="small">
              <Text strong>{s.label}</Text>
              {s.output && (
                <>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>{s.output}</Text>
                </>
              )}
            </Card>
          ))}
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
                    <Button
                      key={opt.label}
                      type="default"
                      onClick={() => onAnswer(opt.label)}
                    >
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
        </Flex>
      ),
    },
  ];

  return (
    <Collapse
      items={items}
      defaultActiveKey={state.status === 'building' || state.status === 'needs-input' ? ['main'] : []}
      size="small"
    />
  );
}
