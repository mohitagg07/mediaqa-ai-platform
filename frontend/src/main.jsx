import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Home       from './pages/Home'
import AuthPage   from './pages/AuthPage'
import Dashboard  from './pages/Dashboard'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/"          element={<Home />} />
        <Route path="/auth"      element={<AuthPage />} />
        <Route path="/dashboard" element={<Dashboard />} />
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
  </React.StrictMode>
)
