import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ControlCenterPage } from './pages/ControlCenterPage'
import { SetupPage } from './pages/SetupPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/session/:sessionId" element={<ControlCenterPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
