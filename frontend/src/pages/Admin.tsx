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
          En construcción — F-007/F-008
        </Typography>
      </CardContent>
    </Card>
  )
}

const tabs: AppLayoutTab[] = [
  { label: 'Resumen', content: <Placeholder title="Resumen" /> },
  { label: 'Inventario', content: <Placeholder title="Inventario" /> },
  { label: 'Predicciones', content: <Placeholder title="Predicciones" /> },
  { label: 'Órdenes de compra', content: <Placeholder title="Órdenes de compra" /> },
  { label: 'Ventas', content: <Placeholder title="Ventas" /> },
]

export default function Admin() {
  return <AppLayout tabs={tabs} />
}
