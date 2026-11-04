import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ArchitecturePage } from './pages/ArchitecturePage'
import { GuidePage } from './pages/GuidePage'
import { ControlCenterPage } from './pages/ControlCenterPage'
import { OrchestrationPage } from './pages/OrchestrationPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { RecoveryPage } from './pages/RecoveryPage'
import { SetupPage } from './pages/SetupPage'
import { SimpleLoopPage } from './pages/SimpleLoopPage'
import { StudentLoopPage } from './pages/StudentLoopPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/projects/:projectId/new" element={<SetupPage />} />
        <Route path="/session/:sessionId" element={<ControlCenterPage />} />
        <Route path="/guide" element={<GuidePage />} />
        <Route path="/student-loop" element={<StudentLoopPage />} />
        <Route path="/simple-loop" element={<SimpleLoopPage />} />
        <Route path="/architecture" element={<ArchitecturePage />} />
        <Route path="/orchestration" element={<OrchestrationPage />} />
        <Route path="/recovery" element={<RecoveryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
