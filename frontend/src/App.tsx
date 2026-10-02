import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Box, Card, CardContent, Typography } from '@mui/material'

function PagePlaceholder({ title, text }: { title: string; text: string }) {
  return (
    <Box
      sx={{
        minHeight: 'calc(100vh - 48px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Card sx={{ minWidth: 320, maxWidth: 480 }}>
        <CardContent>
          <Typography variant="h6">{title}</Typography>
          <Typography variant="body2" color="text.secondary">
            {text}
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route
          path="/login"
          element={
            <Box
              sx={{
                minHeight: '100vh',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Card sx={{ minWidth: 320, maxWidth: 420 }}>
                <CardContent>
                  <Typography variant="h5" align="center">
                    KeepInventory
                  </Typography>
                  <Typography variant="body2" align="center" color="text.secondary">
                    Login — llega en F-006
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          }
        />
        <Route
          path="/admin"
          element={
            <PagePlaceholder
              title="Dashboard del Admin"
              text="En construcción (F-007/F-008)"
            />
          }
        />
        <Route
          path="/empleado"
          element={
            <PagePlaceholder title="Panel del Empleado" text="En construcción (F-009)" />
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
