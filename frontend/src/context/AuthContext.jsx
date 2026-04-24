import { createContext, useContext, useState, useCallback } from 'react'
import { authAPI } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })

  const login = useCallback(async (username, password) => {
    const res = await authAPI.login({ username, password })
    const { access_token } = res.data
    localStorage.setItem('token', access_token)
    localStorage.setItem('user', JSON.stringify({ username }))
    setUser({ username })
    return res.data
  }, [])

  const register = useCallback(async (username, email, password) => {
    return authAPI.register({ username, email, password })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
