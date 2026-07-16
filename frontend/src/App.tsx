import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { PasswordChangedRoute } from './components/PasswordChangedRoute'
import { ProtectedRoute } from './components/ProtectedRoute'
import { RoleRoute } from './components/RoleRoute'
import { AlertsPage } from './pages/AlertsPage'
import { AccessDeniedPage } from './pages/AccessDeniedPage'
import { AuditPage } from './pages/AuditPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import { ChatPage } from './pages/ChatPage'
import { HomeRoute } from './components/HomeRoute'
import { LoginPage } from './pages/LoginPage'
import { IntegrationsPage } from './pages/IntegrationsPage'
import { OwnersPage } from './pages/OwnersPage'
import { PetDetailPage } from './pages/PetDetailPage'
import { PetsPage } from './pages/PetsPage'
import { PlansPage } from './pages/PlansPage'
import { RagQualityPage } from './pages/RagQualityPage'
import { QualityPage } from './pages/QualityPage'
import { SecurityPage } from './pages/SecurityPage'
import { SystemStatusPage } from './pages/SystemStatusPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/change-password" element={<ProtectedRoute><ChangePasswordPage /></ProtectedRoute>} />
      <Route element={<ProtectedRoute><PasswordChangedRoute><AppShell /></PasswordChangedRoute></ProtectedRoute>}>
        <Route index element={<HomeRoute />} />
        <Route path="forbidden" element={<AccessDeniedPage />} />
        <Route path="owners" element={<RoleRoute allowed={['clinic', 'staff']}><OwnersPage /></RoleRoute>} />
        <Route path="pets" element={<RoleRoute allowed={['clinic', 'staff', 'owner']}><PetsPage /></RoleRoute>} />
        <Route path="pets/:petId" element={<RoleRoute allowed={['clinic', 'staff', 'owner']}><PetDetailPage /></RoleRoute>} />
        <Route path="plans" element={<RoleRoute allowed={['clinic', 'staff', 'owner']}><PlansPage /></RoleRoute>} />
        <Route path="alerts" element={<RoleRoute allowed={['clinic', 'staff']}><AlertsPage /></RoleRoute>} />
        <Route path="chat" element={<RoleRoute allowed={['clinic', 'staff', 'owner']}><ChatPage /></RoleRoute>} />
        <Route path="vetia-quality" element={<RoleRoute allowed={['technical']}><RagQualityPage /></RoleRoute>} />
        <Route path="rag-quality" element={<Navigate to="/vetia-quality" replace />} />
        <Route path="quality" element={<RoleRoute allowed={['technical']}><QualityPage /></RoleRoute>} />
        <Route path="integrations" element={<RoleRoute allowed={['technical']}><IntegrationsPage /></RoleRoute>} />
        <Route path="audit" element={<RoleRoute allowed={['technical']}><AuditPage /></RoleRoute>} />
        <Route path="security" element={<RoleRoute allowed={['technical']}><SecurityPage /></RoleRoute>} />
        <Route path="system-status" element={<RoleRoute allowed={['technical']}><SystemStatusPage /></RoleRoute>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
