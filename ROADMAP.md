# Roadmap — KeepInventory

Estado por feature: pendiente → en_curso → hecha. Flujo: el arquitecto escribe la spec en
.specs/, el executor la implementa, se verifican los comandos de la spec y se pausa para
revisión del usuario antes de iniciar la siguiente feature.

| ID | Feature | Criterio principal de aceptación | Estado |
|----|---------|-----------------------------------|--------|
| F-001 | Andamiaje | 3 servicios con /health, frontend base MUI, lint (ruff), typecheck (tsc vía build), tests de ejemplo pasando, start-all.ps1 | hecha |
| F-002 | Semilla de datos | seed.py carga el CSV BigBasket, crea usuarios demo y ~180 días de historial realista (ventas, compras, stock con los 4 estados) | hecha |
| F-003 | Servicio Auth | POST /auth/login emite JWT por rol, GET /auth/me valida token, util de RBAC compartida | hecha |
| F-004 | Backend: inventario (catálogo, stock, compras) y ventas | fusiona las antiguas F-004/F-005/F-006: GET /products con filtros dinámicos y estado calculado, edición parcial de producto y umbrales (admin), alertas, movimientos, órdenes de compra (crear/modificar/eliminar/enviar/cancelar/recibir; recibir suma stock y crea movimientos), POST /sales con descuento atómico por lote vía REST a inventory (409 si no alcanza) y GET /sales con filtros | en_curso |
| F-005 | Analítica | KPIs, tendencia (día/semana/mes), ventas por categoría, top productos, resumen de compras (con llamadas REST a inventory) | pendiente |
| F-006 | Predicciones | regresión lineal + fallback: demanda diaria, fecha estimada de agotamiento, demanda 30 días y reorden sugerido | pendiente |
| F-007 | Frontend: login y ruteo | login funcional, redirect por rol, layout estilo Lightdash | pendiente |
| F-008 | Frontend admin: dashboard | KPIs + gráficas interactivas (filtros de fecha/categoría) + tabla semáforo de stock | pendiente |
| F-009 | Frontend admin: decisión | tabla de predicciones, crear/modificar/enviar órdenes de compra, editar umbrales y productos | pendiente |
| F-010 | Frontend empleado | registrar venta (descuenta stock en vivo), recibir mercancía, catálogo simple | pendiente |
| F-011 | Cierre | README con pasos de demo, verificación end-to-end y pulido final | pendiente |

## Notas
- Datos: catálogo completo BigBasket (~28K filas); ventas/stock/compras simulados solo para
  ~2000 "productos activos" (elegidos por la semilla).
- Los servicios validan el JWT localmente; sales reenvía el JWT del usuario al llamar a
  inventory (mismo RBAC en los endpoints internos).
- 2026-10-01: F-004/F-005/F-006 se fusionaron en la F-004 y las siguientes se renumeraron
  (las specs .specs/F-001..F-003 ya cerradas conservan la numeración antigua).
