import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './context/AuthContext'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import AuthPage from './pages/AuthPage'
import './index.css'

// ── Protected Route ───────────────────────────────────────────────
// Any route wrapped in this redirects to /auth if not logged in.
function ProtectedRoute({ children }) {
  const { user } = useAuth()
  const token = localStorage.getItem('token')

  if (!user && !token) {
    return <Navigate to="/auth" replace />
  }
  return children
}

// ── App ───────────────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="app-shell">
          <Navbar />
          <main className="main-content">
            <Routes>
              {/* Public pages */}
              <Route path="/"     element={<Home />} />
              <Route path="/auth" element={<AuthPage />} />

              {/* Protected — must be logged in */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />

              {/* Catch-all */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>

        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: 'var(--surface)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
              fontFamily: 'var(--font-mono)',
              fontSize: '13px',
            },
          }}
        />
      </BrowserRouter>
    </AuthProvider>
  )
}