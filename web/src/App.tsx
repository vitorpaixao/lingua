import { useEffect, useState, type ReactNode } from 'react';
import { BrowserRouter, Route, Routes, Navigate, useLocation } from 'react-router-dom';
import { ConfigProvider, App as AntdApp, Flex, Spin } from 'antd';
import { XProvider } from '@ant-design/x';
import { IntroPage } from './pages/IntroPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { SettingsPage } from './pages/SettingsPage';
import { ThemeProvider, useTheme } from './lib/theme';
import { buildLinguaTheme } from './theme/tokens';
import { getSettings } from './api/client';

export function App() {
  return (
    <ThemeProvider>
      <ThemedRoot />
    </ThemeProvider>
  );
}

/**
 * First-run gate: until the Credential Vault has a usable Model Connection, every
 * route except /settings redirects to the Settings page in first-run mode.
 */
function RequireSetup({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [configured, setConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    void getSettings()
      .then((s) => setConfigured(s.is_configured))
      .catch(() => setConfigured(true)); // fail open — don't trap the user on API error
  }, [location.pathname]);

  if (configured === null) {
    return (
      <Flex justify="center" align="center" style={{ minHeight: '100vh' }}>
        <Spin size="large" />
      </Flex>
    );
  }
  if (!configured) return <Navigate to="/settings?firstRun=1" replace />;
  return <>{children}</>;
}

function ThemedRoot() {
  const { mode } = useTheme();
  return (
    <ConfigProvider theme={buildLinguaTheme(mode)}>
      <AntdApp style={{ height: '100%' }}>
        <XProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/settings" element={<SettingsPage />} />
              <Route
                path="/"
                element={
                  <RequireSetup>
                    <IntroPage />
                  </RequireSetup>
                }
              />
              <Route
                path="/workspace"
                element={
                  <RequireSetup>
                    <WorkspacePage />
                  </RequireSetup>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </XProvider>
      </AntdApp>
    </ConfigProvider>
  );
}
