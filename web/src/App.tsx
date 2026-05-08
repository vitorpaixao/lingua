import { Routes, Route } from 'react-router-dom'
import { IntroPage } from './pages/IntroPage'
import { WorkspacePage } from './pages/WorkspacePage'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<IntroPage />} />
      <Route path="/workspace" element={<WorkspacePage />} />
    </Routes>
  )
}
