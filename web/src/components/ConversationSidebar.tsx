import { useCallback, useEffect, useState } from 'react';
import { Conversations } from '@ant-design/x';
import type { ConversationsProps } from '@ant-design/x';
import { App as AntdApp, Button, Flex, Input, Tooltip, theme } from 'antd';
import type { GetProp } from 'antd';
import {
  MessageOutlined,
  PlusOutlined,
  CodeSandboxOutlined,
  FileImageOutlined,
  FileSearchOutlined,
} from '@ant-design/icons';
import {
  listConversations,
  createConversation,
  renameConversation,
  archiveConversation,
  deleteConversation,
} from '@/api/client';
import type { Conversation } from '@/types/api';

type ActivePanel = 'chats' | null;
const PANEL_KEY = 'lingua_sidebar_panel';

function loadPanel(): ActivePanel {
  return window.localStorage.getItem(PANEL_KEY) === 'closed' ? null : 'chats';
}

// Placeholder system features — reserved icons for future panels (disabled for now).
const PLACEHOLDERS = [
  { key: 'coding', label: 'AI Coding', icon: <CodeSandboxOutlined /> },
  { key: 'images', label: 'Create Image', icon: <FileImageOutlined /> },
  { key: 'search', label: 'Deep Search', icon: <FileSearchOutlined /> },
];

const DAY = 24 * 60 * 60 * 1000;

/** Date bucket for grouping, computed from an ISO timestamp. */
function bucket(iso: string): string {
  const then = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const t = then.getTime();
  if (t >= startOfToday) return 'Today';
  if (t >= startOfToday - DAY) return 'Yesterday';
  if (t >= startOfToday - 7 * DAY) return 'Previous 7 days';
  return 'Older';
}

/** Activity-bar sidebar: always-visible icon rail + a collapsible panel (the chat list). */
export function ConversationSidebar({
  projectId,
  activeId,
  onSelect,
}: {
  projectId: string;
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  const { modal } = AntdApp.useApp();
  const { token } = theme.useToken();
  const [items, setItems] = useState<Conversation[]>([]);
  const [panel, setPanel] = useState<ActivePanel>(loadPanel);

  const toggleChats = useCallback(() => {
    setPanel((p) => {
      const next: ActivePanel = p === 'chats' ? null : 'chats';
      window.localStorage.setItem(PANEL_KEY, next === null ? 'closed' : 'chats');
      return next;
    });
  }, []);

  const reload = useCallback(async () => {
    const list = await listConversations(projectId);
    setItems(list);
    return list;
  }, [projectId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const onNew = useCallback(async () => {
    const c = await createConversation(projectId);
    await reload();
    onSelect(c.id);
  }, [projectId, reload, onSelect]);

  const fallbackAfterRemoval = useCallback(
    async (removedId: string) => {
      const list = await reload();
      if (removedId !== activeId) return;
      if (list[0]) onSelect(list[0].id);
      else await onNew();
    },
    [reload, activeId, onSelect, onNew],
  );

  const onRename = useCallback(
    (c: Conversation) => {
      let value = c.title;
      modal.confirm({
        title: 'Rename conversation',
        icon: null,
        content: (
          <Input
            defaultValue={c.title}
            autoFocus
            onChange={(e) => {
              value = e.target.value;
            }}
          />
        ),
        onOk: async () => {
          const next = value.trim();
          if (next && next !== c.title) {
            await renameConversation(c.id, next);
            await reload();
          }
        },
      });
    },
    [modal, reload],
  );

  const onArchive = useCallback(
    async (c: Conversation) => {
      await archiveConversation(c.id);
      await fallbackAfterRemoval(c.id);
    },
    [fallbackAfterRemoval],
  );

  const onDelete = useCallback(
    (c: Conversation) => {
      modal.confirm({
        title: 'Delete conversation?',
        content: 'This permanently removes its transcript and agent memory.',
        okText: 'Delete',
        okType: 'danger',
        onOk: async () => {
          await deleteConversation(c.id);
          await fallbackAfterRemoval(c.id);
        },
      });
    },
    [modal, fallbackAfterRemoval],
  );

  const conversationItems: GetProp<ConversationsProps, 'items'> = items.map((c) => ({
    key: c.id,
    label: c.title,
    group: bucket(c.updated_at),
  }));

  const open = panel === 'chats';

  return (
    <Flex style={{ height: '100%' }}>
      {/* Activity bar — always visible */}
      <Flex
        vertical
        align="center"
        gap={4}
        style={{
          width: 52,
          flex: '0 0 52px',
          padding: '8px 0',
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          background: token.colorBgLayout,
        }}
      >
        <Tooltip title="Chats" placement="right">
          <Button
            type={open ? 'primary' : 'text'}
            icon={<MessageOutlined />}
            onClick={toggleChats}
          />
        </Tooltip>
        {PLACEHOLDERS.map((p) => (
          <Tooltip key={p.key} title={`${p.label} — coming soon`} placement="right">
            {/* span wrapper so the tooltip works on a disabled button */}
            <span>
              <Button type="text" icon={p.icon} disabled />
            </span>
          </Tooltip>
        ))}
      </Flex>

      {/* Sidebar panel — only when a panel is active */}
      {open && (
        <Flex
          vertical
          style={{
            width: 248,
            flex: '0 0 248px',
            minHeight: 0,
            borderRight: `1px solid ${token.colorBorderSecondary}`,
            background: token.colorBgContainer,
          }}
        >
          <Flex style={{ padding: 8 }}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              block
              onClick={() => void onNew()}
            >
              New conversation
            </Button>
          </Flex>
          <Flex vertical flex={1} style={{ overflow: 'auto' }}>
            <Conversations
              items={conversationItems}
              activeKey={activeId ?? undefined}
              onActiveChange={(key) => onSelect(key)}
              groupable={{ collapsible: (group: string) => group !== 'Today' }}
              menu={(value) => {
                const c = items.find((x) => x.id === value.key);
                return {
                  items: [
                    { key: 'rename', label: 'Rename' },
                    { key: 'archive', label: 'Archive' },
                    { type: 'divider' as const },
                    { key: 'delete', label: 'Delete', danger: true },
                  ],
                  onClick: ({ key, domEvent }) => {
                    domEvent.stopPropagation();
                    if (!c) return;
                    if (key === 'rename') onRename(c);
                    else if (key === 'archive') void onArchive(c);
                    else if (key === 'delete') onDelete(c);
                  },
                };
              }}
              style={{ flex: 1, overflow: 'auto' }}
            />
          </Flex>
        </Flex>
      )}
    </Flex>
  );
}
