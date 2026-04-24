import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// main.jsx must use App.jsx which has AuthProvider + ProtectedRoute.
// The previous version bypassed App.jsx entirely — that caused
// AuthContext to be undefined → blank screen on /auth and /dashboard.

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
