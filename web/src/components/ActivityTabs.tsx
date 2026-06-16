import { Segmented } from 'antd';
import {
  MessageOutlined,
  CodeSandboxOutlined,
  FileImageOutlined,
  FileSearchOutlined,
} from '@ant-design/icons';

export type ActivityKey = 'chats' | 'coding' | 'images' | 'search';

/** Horizontal activity-feature switcher — replaces the old vertical icon rail.
 *  Only "Chats" is live today; the other three are reserved placeholders. */
const OPTIONS = [
  { value: 'chats', label: 'Chats', icon: <MessageOutlined /> },
  { value: 'coding', label: 'AI Coding', icon: <CodeSandboxOutlined />, disabled: true },
  { value: 'images', label: 'Create Image', icon: <FileImageOutlined />, disabled: true },
  { value: 'search', label: 'Deep Search', icon: <FileSearchOutlined />, disabled: true },
];

export function ActivityTabs() {
  // Value is fixed to 'chats' for now; the other options are disabled placeholders.
  return <Segmented className="lingua-activity-tabs" block value="chats" options={OPTIONS} />;
}
