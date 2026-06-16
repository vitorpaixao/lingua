import { Button, Flex, Space, Tooltip, theme } from 'antd';
import { ArrowLeftOutlined, TranslationOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { ThemeToggle } from '@/components/ThemeToggle';

/** Header over the left column: back to projects, Lingua wordmark, theme toggle. */
export function WorkspaceHeader() {
  const nav = useNavigate();
  const { token } = theme.useToken();

  return (
    <Flex
      justify="space-between"
      align="center"
      style={{
        height: 48,
        padding: '0 8px',
        background: token.colorBgLayout,
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

      <ThemeToggle />
    </Flex>
  );
}
