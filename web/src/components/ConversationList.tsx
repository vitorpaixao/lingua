import { useCallback } from 'react';
import { Conversations } from '@ant-design/x';
import type { ConversationsProps } from '@ant-design/x';
import { App as AntdApp, Button, Flex, Input, theme } from 'antd';
import type { GetProp } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import {
  createConversation,
  renameConversation,
  archiveConversation,
  deleteConversation,
} from '@/api/client';
import type { Conversation } from '@/types/api';

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

/** The conversation thread list (date-grouped, with rename/archive/delete + New).
 *  Rendered inline in the chat column when the conversation selector is toggled open. */
export function ConversationList({
  projectId,
  activeId,
  items,
  reload,
  onSelect,
}: {
  projectId: string;
  activeId: string | null;
  items: Conversation[];
  reload: () => Promise<Conversation[]>;
  onSelect: (id: string) => void;
}) {
  const { modal } = AntdApp.useApp();
  const { token } = theme.useToken();

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

  return (
    <Flex
      vertical
      className="lingua-conversation-list"
      style={{ height: '100%', minHeight: 0, background: token.colorBgLayout }}
    >
      <Flex style={{ padding: 8 }}>
        <Button type="primary" icon={<PlusOutlined />} block onClick={() => void onNew()}>
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
  );
}
