import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntdApp, theme as antdTheme } from 'antd';
import { XProvider } from '@ant-design/x';
import { IntroPage } from './pages/IntroPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { ThemeProvider, useTheme } from './lib/theme';

export function App() {
  return (
    <ThemeProvider>
      <ThemedRoot />
    </ThemeProvider>
  );
}

function ThemedRoot() {
  const { mode } = useTheme();
  return (
    <ConfigProvider
      theme={{
        algorithm:
          mode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: { colorPrimary: '#1677ff' },
      }}
    >
      <AntdApp style={{ height: '100%' }}>
        <XProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<IntroPage />} />
              <Route path="/workspace" element={<WorkspacePage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </XProvider>
      </AntdApp>
    </ConfigProvider>
  );
}
