import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { useAuth } from './context/AuthContext'
import { DataProvider } from './context/DataContext'
import Cameras from './pages/Cameras'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import LiveWall from './pages/LiveWall'
import Login from './pages/Login'
import Responder from './pages/Responder'
import Units from './pages/Units'

export default function App() {
  const { user, loading, isStaff } = useAuth()

  if (loading) return <div className="flex h-full items-center justify-center mono text-xs uppercase tracking-widest text-slate-500">Initialising console…</div>
  if (!user) return <Login />

  return (
    <DataProvider>
      <Routes>
        <Route element={<Layout />}>
          {isStaff ? (
            <>
              <Route index element={<Dashboard />} />
              <Route path="live" element={<LiveWall />} />
              <Route path="cameras" element={<Cameras />} />
              <Route path="units" element={<Units />} />
              <Route path="history" element={<History />} />
              <Route path="responder" element={<Responder />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </>
          ) : (
            <>
              <Route path="responder" element={<Responder />} />
              <Route path="*" element={<Navigate to="/responder" replace />} />
            </>
          )}
        </Route>
      </Routes>
    </DataProvider>
  )
}
