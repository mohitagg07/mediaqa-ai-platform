import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LogOut, LayoutDashboard, Zap } from 'lucide-react'
import './Navbar.css'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <nav className="navbar">
      <div className="navbar-inner container">
        <Link to="/" className="navbar-brand">
          <span className="brand-icon"><Zap size={18} /></span>
          <span className="brand-text">Media<span className="brand-accent">QA</span></span>
        </Link>

        <div className="navbar-actions">
          {user ? (
            <>
              <Link to="/dashboard" className={`btn btn-ghost ${location.pathname === '/dashboard' ? 'active' : ''}`}>
                <LayoutDashboard size={15} />
                Dashboard
              </Link>
              <span className="navbar-user mono">@{user.username}</span>
              <button onClick={handleLogout} className="btn btn-ghost">
                <LogOut size={15} />
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/auth" className="btn btn-primary">
                Sign In
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  )
}
