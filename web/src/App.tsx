import { useState } from 'react'
import { Routes, Route, Link } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import { ProLayout } from '@ant-design/pro-components'
import { BulbFilled, BulbOutlined } from '@ant-design/icons'
import { IntroPage } from './pages/IntroPage'
import { WorkspacePage } from './pages/WorkspacePage'

const routeConfig = {
  routes: [
    { path: '/', name: 'Projects' },
    { path: '/workspace', name: 'Workspace' },
  ],
}

export function App() {
  const [isDark, setIsDark] = useState(true)
  const [collapsed, setCollapsed] = useState(false)

  return (
    <ConfigProvider theme={{ algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm }}>
      <ProLayout
        title="Lingua"
        layout="side"
        route={routeConfig}
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ height: '100vh' }}
        contentStyle={{ padding: 0, height: '100%', overflow: 'hidden' }}
        menuItemRender={(item, dom) => <Link to={item.path ?? '/'}>{dom}</Link>}
        menuFooterRender={() => (
          <div
            style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
            onClick={() => setIsDark(d => !d)}
          >
            {isDark ? <BulbOutlined /> : <BulbFilled />}
            {!collapsed && <span>{isDark ? 'Light' : 'Dark'}</span>}
          </div>
        )}
      >
        <Routes>
          <Route path="/" element={<IntroPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
        </Routes>
      </ProLayout>
    </ConfigProvider>
  )
}
