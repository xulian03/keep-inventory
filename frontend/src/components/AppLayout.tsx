import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  Tab,
  Tabs,
  Toolbar,
  Typography,
} from '@mui/material'
import { useAuth, type Role } from '../auth/AuthContext'

export interface AppLayoutTab {
  label: string
  content: ReactNode
}

interface AppLayoutProps {
  tabs: AppLayoutTab[]
}

const roleLabels: Record<Role, string> = {
  admin: 'Dueño/Admin',
  empleado: 'Empleado/Vendedor',
}

export default function AppLayout({ tabs }: AppLayoutProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [index, setIndex] = useState(0)

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="static" color="inherit" elevation={1}>
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, flexGrow: 1 }}>
            KeepInventory
          </Typography>
          {user && (
            <Typography variant="body2" color="text.secondary">
              {user.name}
            </Typography>
          )}
          {user && <Chip size="small" color="primary" label={roleLabels[user.role]} />}
          <Button color="inherit" onClick={handleLogout}>
            Cerrar sesión
          </Button>
        </Toolbar>
      </AppBar>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
        <Container maxWidth="lg">
          <Tabs
            value={index}
            onChange={(_event, value: number) => setIndex(value)}
            variant="scrollable"
            scrollButtons="auto"
          >
            {tabs.map((tab) => (
              <Tab key={tab.label} label={tab.label} />
            ))}
          </Tabs>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ py: 3 }}>
        {tabs[index]?.content}
      </Container>
    </Box>
  )
}
