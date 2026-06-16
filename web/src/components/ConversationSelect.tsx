import { Button } from 'antd';
import { DownOutlined, UpOutlined } from '@ant-design/icons';

/** Full-width selector at the top of the chat column. Clicking it toggles the chat
 *  column between the active chat and the conversation list (rendered by the parent). */
export function ConversationSelect({
  title,
  open,
  onToggle,
}: {
  title: string;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <Button
      block
      onClick={onToggle}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
    >
      <span
        style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
      >
        {title}
      </span>
      {open ? <UpOutlined /> : <DownOutlined />}
    </Button>
  );
}
