import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function ProtectedRoute({
  children,
  adminOnly = false,
}: {
  children: ReactNode
  adminOnly?: boolean
}) {
  const { user, loading } = useAuth()

  if (loading) {
    return <p className="page-status">Loading…</p>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (adminOnly && user.role !== 'admin') {
    return <Navigate to="/documents" replace />
  }
  return <>{children}</>
}
