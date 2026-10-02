# KeepInventory — Guía para agentes

Sistema web de control de inventario para una tienda (proyecto universitario, entrega en un día):
microservicios REST + frontend React. Prioridad: funcional, simple, demostrable.

## Stack
- Backend: 3 microservicios FastAPI, cada uno con su SQLite y su paquete Python propio:
  - auth (puerto 8001, auth.db): usuarios, roles, emisión de JWT.
  - inventory (puerto 8002, inventory.db): productos, stock, umbrales, estados, movimientos,
    proveedores, órdenes de compra y recepciones.
  - sales (puerto 8003, sales.db): ventas, histórico, KPIs, analítica, resumen de compras
    y predicciones (regresión lineal con fallback de media móvil).
- Frontend: React + Vite (TypeScript) + MUI + Recharts en el puerto 5173, estilo Lightdash
  (tarjetas blancas, tipografía Inter, paleta violeta/teal/ámbar).
- Comunicación: solo HTTP/JSON. sales→inventory por REST interno (descuento de stock y
  consultas de catálogo, reenviando el JWT del usuario). JWT HS256 con secreto compartido.

## Estructura
- services/<svc>/src/<paquete>/ : código del servicio (main.py, config.py, luego models/routers).
- services/<svc>/tests/ : pytest con TestClient.
- frontend/src/ : páginas (Login, Admin, Empleado), auth/ (AuthContext + useAuth),
  components/ (AppLayout, RequireRole), api/ (client.ts + shared.ts: tipos/helpers
  compartidos), admin/ y empleado/ (paneles por pestaña), theme.ts.
- scripts/seed.py : semilla de datos (CSV BigBasket en data/ + historial simulado);
  scripts/tests/ : tests de la semilla (invariants de ledger y calibración).
- .specs/F-XXX-*.md : specs por feature; fuente de verdad del trabajo.
- docs/ARCHITECTURE.md : arquitectura completa; fuente del documento de diseño.

## Reglas de trabajo
- El arquitecto escribe specs en .specs/; el executor las implementa paso a paso; nada fuera
  de spec sin aprobación del usuario.
- Una feature solo termina con: tests verdes, lint limpio, build de frontend OK (si aplica)
  y servicios arrancando.
- Actualizar ROADMAP.md al cambiar el estado de cada feature.
- UI en español, incluidos los VALORES de enum en API/BD (state, movement_type,
  reason, status de orden: agotado/bajo/disponible/exceso, entrada/salida,
  compra/ajuste/venta, borrador/enviada/recibida/cancelada). Moneda "$" genérico.
  Fechas ISO-8601. Paginación server-side (50/página, máx 100).

## Comandos (PowerShell, desde la raíz)
- Variables de entorno opcionales (todas con defaults en services/*/src/*/config.py, la
  demo funciona sin .env): JWT_SECRET, AUTH_PORT, INVENTORY_PORT, SALES_PORT,
  INVENTORY_URL, FRONTEND_URL, AUTH_DB, INVENTORY_DB, SALES_DB.
- Setup Python: python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt
- Setup frontend: cd frontend ; npm install
- Lint: .venv\Scripts\ruff check services scripts
- Tests: .venv\Scripts\pytest -q (testpaths: services + scripts/tests)
- Semilla (requiere CSV en data/): .venv\Scripts\python scripts\seed.py (recrea las
  3 BDs desde cero en la raíz; determinista salvo fechas relativas a hoy)
- Levantar todo (abre 4 ventanas): .\start-all.ps1
- Warm-up tras arrancar (este equipo encarece conexiones nuevas y la 1.ª ejecución de
  sklearn con el AV): abre una vez el dashboard (o llama 1 vez a /analytics/kpis y
  /predictions); después todo responde en centenas de ms.
- Salud: Invoke-WebRequest http://localhost:8001/health (ídem :8002, :8003)

## Credenciales demo (creadas por la semilla)
- admin@tienda.com / admin123 (Dueño/Admin)
- empleado@tienda.com / empleado123 (Empleado/Vendedor)
- vendedor2@tienda.com / vendedor123 (Empleado/Vendedor)
