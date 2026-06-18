import { Button, Flex, Select, Tooltip } from 'antd';
import { UnorderedListOutlined } from '@ant-design/icons';
import type { Conversation } from '@/types/api';

/** Row at the top of the chat column: a Select for quick-switching between
 *  conversations, plus a button that toggles the full conversation list
 *  (rendered by the parent in place of the chat). */
export function ConversationSelect({
  items,
  value,
  onSelect,
  open,
  onToggle,
}: {
  items: Conversation[];
  value: string | null;
  onSelect: (id: string) => void;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <Flex className="lingua-conversation-select" gap={8} align="center">
      <Select
        style={{ flex: 1 }}
        value={value ?? undefined}
        onChange={onSelect}
        options={items.map((c) => ({ value: c.id, label: c.title }))}
        placeholder="Conversations"
      />
      <Tooltip title="Conversations">
        <Button
          icon={<UnorderedListOutlined />}
          type={open ? 'primary' : 'default'}
          onClick={onToggle}
          style={open ? undefined : { background: 'transparent' }}
        />
      </Tooltip>
    </Flex>
  );
}
