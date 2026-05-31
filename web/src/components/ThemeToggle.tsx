import { Button, Tooltip } from 'antd';
import { BulbFilled, BulbOutlined } from '@ant-design/icons';
import { useTheme } from '@/lib/theme';

export function ThemeToggle() {
  const { mode, toggle } = useTheme();
  const isDark = mode === 'dark';
  return (
    <Tooltip title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}>
      <Button
        type="text"
        icon={isDark ? <BulbFilled /> : <BulbOutlined />}
        onClick={toggle}
        aria-label="Toggle color mode"
      />
    </Tooltip>
  );
}
