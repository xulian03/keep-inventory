# Roadmap — KeepInventory

Estado por feature: pendiente → en_curso → hecha. Flujo: el arquitecto escribe la spec en
.specs/, el executor la implementa, se verifican los comandos de la spec y se pausa para
revisión del usuario antes de iniciar la siguiente feature.

| ID | Feature | Criterio principal de aceptación | Estado |
|----|---------|-----------------------------------|--------|
| F-001 | Andamiaje | 3 servicios con /health, frontend base MUI, lint (ruff), typecheck (tsc vía build), tests de ejemplo pasando, start-all.ps1 | pendiente |
| F-002 | Semilla de datos | seed.py carga el CSV BigBasket, crea usuarios demo y ~180 días de historial realista (ventas, compras, stock con los 4 estados) | pendiente |
| F-003 | Servicio Auth | POST /auth/login emite JWT por rol, GET /auth/me valida token, util de RBAC compartida | pendiente |
| F-004 | Inventario: catálogo y stock | GET /products con filtros dinámicos y estado calculado, umbrales editables (admin), alertas, movimientos, entrada manual | pendiente |
| F-005 | Inventario: compras | proveedores + órdenes de compra (crear/modificar/enviar/cancelar/recibir); recibir suma stock y crea movimientos | pendiente |
| F-006 | Servicio Ventas | POST /sales descuenta stock vía REST a inventory (rechaza si no alcanza), GET /sales histórico con filtros | pendiente |
| F-007 | Analítica | KPIs, tendencia (día/semana/mes), ventas por categoría, top productos, resumen de compras (con llamadas REST a inventory) | pendiente |
| F-008 | Predicciones | regresión lineal + fallback: demanda diaria, fecha estimada de agotamiento, demanda 30 días y reorden sugerido | pendiente |
| F-009 | Frontend: login y ruteo | login funcional, redirect por rol, layout estilo Lightdash | pendiente |
| F-010 | Frontend admin: dashboard | KPIs + gráficas interactivas (filtros de fecha/categoría) + tabla semáforo de stock | pendiente |
| F-011 | Frontend admin: decisión | tabla de predicciones, crear/modificar/enviar órdenes de compra, editar umbrales | pendiente |
| F-012 | Frontend empleado | registrar venta (descuenta stock en vivo), recibir mercancía, catálogo simple | pendiente |
| F-013 | Cierre | README con pasos de demo, verificación end-to-end y pulido final | pendiente |

## Notas
- Datos: catálogo completo BigBasket (~28K filas); ventas/stock/compras simulados solo para
  ~2000 "productos activos" (elegidos por la semilla).
- Los servicios validan el JWT localmente; sales reenvía el JWT del usuario al llamar a
  inventory (mismo RBAC en los endpoints internos).
