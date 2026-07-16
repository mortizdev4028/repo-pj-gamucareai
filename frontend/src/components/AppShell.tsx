import { useState } from 'react'
import {
  AppBar, Avatar, Box, Chip, Divider, Drawer, IconButton, List, ListItemButton,
  ListItemIcon, ListItemText, Toolbar, Tooltip, Typography, useMediaQuery
} from '@mui/material'
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded'
import PetsRoundedIcon from '@mui/icons-material/PetsRounded'
import HealthAndSafetyRoundedIcon from '@mui/icons-material/HealthAndSafetyRounded'
import ChatRoundedIcon from '@mui/icons-material/ChatRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import MenuRoundedIcon from '@mui/icons-material/MenuRounded'
import PeopleAltRoundedIcon from '@mui/icons-material/PeopleAltRounded'
import ScienceRoundedIcon from '@mui/icons-material/ScienceRounded'
import AssessmentRoundedIcon from '@mui/icons-material/AssessmentRounded'
import SyncAltRoundedIcon from '@mui/icons-material/SyncAltRounded'
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded'
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded'
import MonitorHeartRoundedIcon from '@mui/icons-material/MonitorHeartRounded'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTheme } from '@mui/material/styles'
import { useAuth } from '../auth/AuthContext'
import logo from '../assets/logo.png'
import { APP_ENV, APP_VERSION, RELEASE_LABEL } from '../version'

const drawerWidth = 252
const labels: Record<string, string> = {
  clinic: 'Clinica', staff: 'Personal · solo lectura', owner: 'Propietario', technical: 'Tecnico'
}

export function AppShell() {
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('md'))
  const [open, setOpen] = useState(false)
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const businessItems = [
    { label: 'Resumen', path: '/', icon: <DashboardRoundedIcon /> },
    ...(user?.role !== 'owner' ? [{ label: 'Clientes', path: '/owners', icon: <PeopleAltRoundedIcon /> }] : []),
    { label: user?.role === 'owner' ? 'Mis mascotas' : 'Mascotas', path: '/pets', icon: <PetsRoundedIcon /> },
    { label: 'Planes LifeCare', path: '/plans', icon: <HealthAndSafetyRoundedIcon /> },
    ...(user?.role !== 'owner' ? [{ label: 'Avisos preventivos', path: '/alerts', icon: <WarningAmberRoundedIcon /> }] : []),
    { label: 'VetIA', path: '/chat', icon: <ChatRoundedIcon /> },
  ]

  const technicalItems = [
    { label: 'Calidad de VetIA', path: '/vetia-quality', icon: <ScienceRoundedIcon /> },
    { label: 'Validacion del MVP', path: '/quality', icon: <AssessmentRoundedIcon /> },
    { label: 'Integracion Wakyma', path: '/integrations', icon: <SyncAltRoundedIcon /> },
    { label: 'Auditoria', path: '/audit', icon: <FactCheckRoundedIcon /> },
    { label: 'Seguridad', path: '/security', icon: <SecurityRoundedIcon /> },
    { label: 'Estado tecnico', path: '/system-status', icon: <MonitorHeartRoundedIcon /> },
  ]

  const items = user?.role === 'technical' ? technicalItems : businessItems

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 1, py: 1.5 }}>
        <Avatar src={logo} variant="rounded" sx={{ width: 52, height: 52, bgcolor: 'transparent' }} />
        <Box>
          <Typography fontWeight={850} fontSize={20}>GamuCare AI</Typography>
          <Typography variant="caption" color="text.secondary">Salud siempre al dia</Typography>
          <Typography variant="caption" color="text.disabled" display="block">v{APP_VERSION}</Typography>
        </Box>
      </Box>
      <Divider sx={{ my: 1.5 }} />
      <List sx={{ display: 'grid', gap: 0.5 }}>
        {items.map((item) => (
          <ListItemButton
            key={item.path}
            selected={location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path))}
            onClick={() => { navigate(item.path); setOpen(false) }}
            sx={{ borderRadius: 3 }}
          >
            <ListItemIcon sx={{ minWidth: 42 }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
      <Box sx={{ mt: 'auto', p: 1 }}>
        <Chip label={labels[user?.role || 'owner']} color="primary" variant="outlined" sx={{ mb: 1 }} />
        <Typography variant="body2" fontWeight={700} noWrap>{user?.email}</Typography>
        <ListItemButton onClick={() => void logout()} sx={{ mt: 1, borderRadius: 3 }}>
          <ListItemIcon sx={{ minWidth: 42 }}><LogoutRoundedIcon /></ListItemIcon>
          <ListItemText primary="Cerrar sesion" />
        </ListItemButton>
      </Box>
    </Box>
  )

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {isMobile ? (
        <Drawer open={open} onClose={() => setOpen(false)} ModalProps={{ keepMounted: true }} sx={{ '& .MuiDrawer-paper': { width: drawerWidth } }}>
          {drawer}
        </Drawer>
      ) : (
        <Drawer variant="permanent" sx={{ width: drawerWidth, '& .MuiDrawer-paper': { width: drawerWidth, borderRight: 0 } }}>
          {drawer}
        </Drawer>
      )}
      <Box component="main" sx={{ flexGrow: 1, minWidth: 0 }}>
        <AppBar position="sticky" elevation={0} color="transparent" sx={{ backdropFilter: 'blur(12px)', borderBottom: '1px solid rgba(124,58,237,.08)' }}>
          <Toolbar>
            {isMobile && (
              <Tooltip title="Abrir menu"><IconButton onClick={() => setOpen(true)}><MenuRoundedIcon /></IconButton></Tooltip>
            )}
            <Typography variant="h6" sx={{ ml: isMobile ? 1 : 0, fontWeight: 800 }}>{user?.role === 'technical' ? 'Administracion tecnica' : 'Panel de salud'}</Typography>
            <Box sx={{ ml: 'auto', display: 'flex', gap: 1, alignItems: 'center' }}>
              <Chip size="small" label={APP_ENV.toUpperCase()} color="warning" variant="outlined" />
              {!isMobile && <Chip size="small" label={RELEASE_LABEL} variant="outlined" />}
            </Box>
          </Toolbar>
        </AppBar>
        <Box sx={{ p: { xs: 2, sm: 3, lg: 4 }, maxWidth: 1500, mx: 'auto' }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  )
}
