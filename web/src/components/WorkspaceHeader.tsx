import { Button, Flex, Space, Tooltip, theme } from 'antd';
import {
  ArrowLeftOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  TranslationOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { ThemeToggle } from '@/components/ThemeToggle';

/** Header over the left column (activity bar + sidebar + chat):
 *  back to projects, logo, sidebar-collapse toggle, theme toggle. */
export function WorkspaceHeader({
  panelOpen,
  onTogglePanel,
}: {
  panelOpen: boolean;
  onTogglePanel: () => void;
}) {
  const nav = useNavigate();
  const { token } = theme.useToken();

  return (
    <Flex
      justify="space-between"
      align="center"
      style={{
        height: 48,
        padding: '0 8px',
        background: token.colorBgContainer,
        borderBottom: `1px solid ${token.colorBorderSecondary}`,
        flexShrink: 0,
      }}
    >
      <Space size={4}>
        <Tooltip title="Back to projects">
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => nav('/')} />
        </Tooltip>
        <Space size={6}>
          <TranslationOutlined style={{ color: token.colorPrimary, fontSize: 18 }} />
          <strong>Lingua</strong>
        </Space>
      </Space>

      <Space size={4}>
        <Tooltip title={panelOpen ? 'Collapse sidebar' : 'Expand sidebar'}>
          <Button
            type="text"
            icon={panelOpen ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />}
            onClick={onTogglePanel}
          />
        </Tooltip>
        <ThemeToggle />
      </Space>
    </Flex>
  );
}
