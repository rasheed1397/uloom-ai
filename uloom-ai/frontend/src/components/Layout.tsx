import type { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">Uloom AI</span>
        {user && (
          <nav className="app-nav">
            <NavLink to="/documents">Documents</NavLink>
            <NavLink to="/conversations">Conversations</NavLink>
            {user.role === 'admin' && <NavLink to="/admin">Admin</NavLink>}
            <NavLink to="/profile" className="app-user">
              {user.email}
            </NavLink>
            <button type="button" onClick={handleLogout}>
              Log out
            </button>
          </nav>
        )}
      </header>
      <main className="app-main">{children}</main>
    </div>
  )
}
