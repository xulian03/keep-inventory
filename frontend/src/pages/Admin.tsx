import { useState } from 'react'
import { Card, CardContent, Typography } from '@mui/material'
import AppLayout, { type AppLayoutTab } from '../components/AppLayout'
import InventarioPanel from '../admin/InventarioPanel'
import ResumenPanel from '../admin/ResumenPanel'
import type { InventoryState } from '../admin/api'

const INVENTARIO_TAB = 1

function Placeholder({ title }: { title: string }) {
  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          En construcción — F-008/F-010
        </Typography>
      </CardContent>
    </Card>
  )
}

export default function Admin() {
  const [tab, setTab] = useState(0)
  const [inventoryState, setInventoryState] = useState('')

  const handleStateClick = (state: InventoryState) => {
    setInventoryState(state)
    setTab(INVENTARIO_TAB)
  }

  const tabs: AppLayoutTab[] = [
    { label: 'Resumen', content: <ResumenPanel onStateClick={handleStateClick} /> },
    { label: 'Inventario', content: <InventarioPanel initialState={inventoryState} /> },
    { label: 'Predicciones', content: <Placeholder title="Predicciones" /> },
    { label: 'Órdenes de compra', content: <Placeholder title="Órdenes de compra" /> },
    { label: 'Ventas', content: <Placeholder title="Ventas" /> },
  ]

  return <AppLayout tabs={tabs} value={tab} onIndexChange={setTab} />
}
