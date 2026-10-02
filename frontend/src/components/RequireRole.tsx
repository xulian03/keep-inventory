import { type ReactNode } from 'react'
import { Box } from '@mui/material'
import { Navigate } from 'react-router-dom'
import { useAuth, type Role } from '../auth/AuthContext'

interface RequireRoleProps {
  role: Role
  children: ReactNode
}

export default function RequireRole({ role, children }: RequireRoleProps) {
  const { user, ready } = useAuth()

  if (!ready) {
    return <Box sx={{ minHeight: '100vh' }} />
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (user.role !== role) {
    return <Navigate to={user.role === 'admin' ? '/admin' : '/empleado'} replace />
  }

  return <>{children}</>
}
