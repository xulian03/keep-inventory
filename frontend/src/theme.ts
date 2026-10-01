import { createTheme } from '@mui/material/styles'

// Paleta Lightdash (docs/ARCHITECTURE.md §9)
export const chartColors = ['#7C3AED', '#14B8A6', '#F59E0B', '#EC4899', '#3B82F6', '#8B5CF6']

const theme = createTheme({
  palette: {
    primary: { main: '#7C3AED' },
    secondary: { main: '#14B8A6' },
    success: { main: '#10B981' },
    warning: { main: '#F59E0B' },
    error: { main: '#EF4444' },
    background: { default: '#F7F8FA', paper: '#FFFFFF' },
    text: { primary: '#1F2430', secondary: '#6B7280' },
  },
  typography: {
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
  },
  shape: {
    borderRadius: 12,
  },
})

export default theme
