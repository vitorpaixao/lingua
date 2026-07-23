import { useState } from 'react';
import { Avatar, ConfigProvider, theme as antdTheme } from 'antd';
import { StyleProvider } from '@ant-design/cssinjs';
import { Bubble, Sender, XProvider } from '@ant-design/x';
import { useTheme } from '@/lib/theme';
import { buildAntdTheme } from '@/theme/tokens';

/**
 * The chat area is the ONE exception to the shadcn-only rule: it keeps Ant
 * Design X (Bubble.List + Sender), exactly as the shipped web/ app does.
 *
 * It is wrapped in its own antd ConfigProvider + XProvider so antd's CSS-in-JS
 * scopes here, while the rest of the shell is pure shadcn/Tailwind. The antd
 * theme is built from the same token source (theme/tokens.ts) and the same
 * dark/light mode as the shadcn shell, so the two stay visually aligned.
 *
 * StyleProvider `layer` puts antd's styles in the `antd` CSS cascade layer so
 * the shell's Tailwind preflight (layer `tailwind-base`, declared first) cannot
 * clobber antd's component borders/resets inside the chat. See globals.css /
 * ADR-0005.
 */

const avatarStyle = { background: '#efdbff', color: '#531dab' } as const;

const role = {
  ai: {
    placement: 'start' as const,
    avatar: <Avatar style={avatarStyle}>L</Avatar>,
  },
  user: {
    placement: 'end' as const,
    variant: 'outlined' as const,
    avatar: <Avatar style={avatarStyle}>U</Avatar>,
  },
};

const items = [
  {
    key: '1',
    role: 'ai',
    content:
      'This is a long text message to show the multiline view of the bubble component. This is a long text message to show the multiline view of the bubble component.',
  },
  { key: '2', role: 'ai', content: 'Good morning, how are you?' },
  { key: '3', role: 'user', content: 'Good morning, how are you?' },
  { key: '4', role: 'user', content: 'Good morning, how are you?' },
];

export function ChatPanel() {
  const { mode } = useTheme();
  const [value, setValue] = useState('');

  const config = {
    ...buildAntdTheme(mode),
    algorithm:
      mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
  };

  return (
    <StyleProvider layer>
      <ConfigProvider theme={config}>
        <XProvider>
          <div
            data-fig="chat"
            className="flex h-full w-[400px] shrink-0 flex-col border-r border-sidebar-border"
          >
            <div className="flex min-h-0 flex-1 flex-col justify-end gap-4 overflow-y-auto p-4">
              <Bubble.List
                autoScroll
                role={role}
                items={items}
                style={{ width: '100%' }}
              />
              <Sender
                value={value}
                onChange={setValue}
                onSubmit={() => setValue('')}
                placeholder="Type to search"
              />
            </div>
          </div>
        </XProvider>
      </ConfigProvider>
    </StyleProvider>
  );
}
