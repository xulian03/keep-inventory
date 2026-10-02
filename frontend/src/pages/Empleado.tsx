import { Card, CardContent, Typography } from '@mui/material'
import AppLayout, { type AppLayoutTab } from '../components/AppLayout'

function Placeholder({ title }: { title: string }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          En construcción — F-009
        </Typography>
      </CardContent>
    </Card>
  )
}

const tabs: AppLayoutTab[] = [
  { label: 'Registrar venta', content: <Placeholder title="Registrar venta" /> },
  { label: 'Recibir mercancía', content: <Placeholder title="Recibir mercancía" /> },
  { label: 'Catálogo', content: <Placeholder title="Catálogo" /> },
]

export default function Empleado() {
  return <AppLayout tabs={tabs} />
}
