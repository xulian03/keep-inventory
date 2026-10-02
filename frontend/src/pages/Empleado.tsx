import AppLayout, { type AppLayoutTab } from '../components/AppLayout'
import RegistrarVentaPanel from '../empleado/RegistrarVentaPanel'
import RecibirMercanciaPanel from '../empleado/RecibirMercanciaPanel'
import CatalogoPanel from '../empleado/CatalogoPanel'

const tabs: AppLayoutTab[] = [
  { label: 'Registrar venta', content: <RegistrarVentaPanel /> },
  { label: 'Recibir mercancía', content: <RecibirMercanciaPanel /> },
  { label: 'Catálogo', content: <CatalogoPanel /> },
]

export default function Empleado() {
  return <AppLayout tabs={tabs} />
}
