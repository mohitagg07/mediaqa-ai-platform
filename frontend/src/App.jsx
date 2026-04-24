import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from './context/AuthContext'
import Home      from './pages/Home'
import Dashboard from './pages/Dashboard'
import AuthPage  from './pages/AuthPage'
import './index.css'

// Dashboard is NOT protected — users can use it without login.
// Auth is optional (bonus feature), not a gate.
// This matches the assignment requirement: auth is a bonus, not mandatory.

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/"          element={<Home />} />
          <Route path="/auth"      element={<AuthPage />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="*"          element={<Navigate to="/" replace />} />
        </Routes>

        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: 'var(--bg-2)',
              color: 'var(--text)',
              border: '1px solid var(--border-md)',
              fontFamily: 'var(--font)',
              fontSize: '0.855rem',
              borderRadius: '10px',
            },
            success: { iconTheme: { primary: 'var(--green)', secondary: 'var(--bg)' } },
            error:   { iconTheme: { primary: 'var(--red)',   secondary: 'var(--bg)' } },
          }}
        />
      </BrowserRouter>
    </AuthProvider>
  )
}
