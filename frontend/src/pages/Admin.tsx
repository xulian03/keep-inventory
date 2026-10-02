import { useState } from 'react'
import AppLayout, { type AppLayoutTab } from '../components/AppLayout'
import InventarioPanel from '../admin/InventarioPanel'
import OrdenesPanel from '../admin/OrdenesPanel'
import PrediccionesPanel from '../admin/PrediccionesPanel'
import ResumenPanel from '../admin/ResumenPanel'
import VentasPanel from '../admin/VentasPanel'
import type { InventoryState } from '../api/shared'

const INVENTARIO_TAB = 1

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
    { label: 'Predicciones', content: <PrediccionesPanel /> },
    { label: 'Órdenes de compra', content: <OrdenesPanel /> },
    { label: 'Ventas', content: <VentasPanel /> },
  ]

  return <AppLayout tabs={tabs} value={tab} onIndexChange={setTab} />
}
