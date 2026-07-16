import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#7c3aed' },
    secondary: { main: '#ec4899' },
    warning: { main: '#f59e0b' },
    info: { main: '#64748b' },
    background: { default: '#f8f7fc', paper: '#ffffff' }
  },
  shape: { borderRadius: 16 },
  typography: {
    fontFamily: 'Inter, Segoe UI, Arial, sans-serif',
    h1: { fontWeight: 800 },
    h2: { fontWeight: 750 },
    h3: { fontWeight: 700 },
    button: { textTransform: 'none', fontWeight: 700 }
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 14px 35px rgba(80, 60, 120, 0.10)',
          border: '1px solid rgba(124, 58, 237, 0.08)'
        }
      }
    },
    MuiButton: {
      styleOverrides: { root: { borderRadius: 12, paddingInline: 18 } }
    }
  }
})
