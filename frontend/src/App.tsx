import { Routes, Route, Navigate } from 'react-router-dom'

import Layout from '@/components/Layout'
import RequireAuth from '@/components/RequireAuth'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import CoreLoop from '@/pages/CoreLoop'
import IncomeEngine from '@/pages/IncomeEngine'
import Codex from '@/pages/Codex'
import Protocols from '@/pages/Protocols'
import Agents from '@/pages/Agents'
import Governance from '@/pages/Governance'
import OutputEngine from '@/pages/OutputEngine'
import Settings from '@/pages/Settings'
import NotFound from '@/pages/NotFound'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="*"
        element={
          <RequireAuth>
            <Layout>
              <Routes>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/core-loop" element={<CoreLoop />} />
                <Route path="/income-engine" element={<IncomeEngine />} />
                <Route path="/codex" element={<Codex />} />
                <Route path="/protocols" element={<Protocols />} />
                <Route path="/agents" element={<Agents />} />
                <Route path="/governance" element={<Governance />} />
                <Route path="/output-engine" element={<OutputEngine />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Layout>
          </RequireAuth>
        }
      />
    </Routes>
  )
}

export default App
