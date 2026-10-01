# Spec F-001 — Andamiaje

## Objetivo
Dejar el repositorio listo para construir las demás features en paralelo: estructura de los
3 microservicios con esqueletos corriendo (GET /health), frontend base con Vite+MUI+Recharts
y tema Lightdash, lint (ruff), typecheck (tsc vía build del frontend), tests de ejemplo
pasando (pytest) y script de arranque start-all.ps1. Al final de esta spec NO existe nada
de negocio: solo estructura y verificación.

## Archivos afectados
- Actualizar: .gitignore (añadir .venv/, __pycache__/, *.db, .pytest_cache/, .ruff_cache/,
  node_modules/, frontend/dist/)
- Nuevos raíz: .env.example, pyproject.toml, requirements.txt, conftest.py, start-all.ps1,
  data/.gitkeep
- Nuevo servicio auth: services/auth/requirements.txt, services/auth/src/auth/{__init__.py,
  main.py, config.py}, services/auth/tests/test_health.py
- Nuevo servicio inventory: services/inventory/requirements.txt,
  services/inventory/src/inventory/{__init__.py, main.py, config.py},
  services/inventory/tests/test_health.py
- Nuevo servicio sales: services/sales/requirements.txt, services/sales/src/sales/
  {__init__.py, main.py, config.py}, services/sales/tests/test_health.py
- Nuevo frontend: proyecto Vite react-ts en frontend/ con deps @mui/material,
  @emotion/react, @emotion/styled, @mui/x-data-grid, recharts, react-router-dom;
  src/theme.ts, src/api/client.ts, rutas placeholder /login, /admin, /empleado.

## Decisiones técnicas concretas
- Paquetes Python únicos por servicio (auth, inventory, sales) bajo src/ para que los tests
  conjuntos no colisionen en imports.
- Cada config.py: carga .env de la raíz si existe (python-dotenv) con defaults que hacen
  la demo funcionar SIN .env: puertos 8001/8002/8003, INVENTORY_URL=http://localhost:8002,
  JWT_SECRET=dev-secret-keep-inventory, CORS http://localhost:5173.
- Cada main.py: FastAPI + CORS + GET /health → {"service": "<nombre>", "status": "ok"}.
- Frontend en TypeScript; client.ts con URLs base por servicio (default
  http://localhost:800X, override con VITE_AUTH_URL/VITE_INVENTORY_URL/VITE_SALES_URL).
- requirements.txt raíz = unión de los 3 servicios + pandas (semilla) + dev (pytest, ruff,
  httpx). Cada servicio además lleva su propio requirements.txt (historia de microservicio).

## Pasos atómicos
1. Config raíz: actualizar .gitignore, crear .env.example, pyproject.toml (ruff
   line-length=100, target py310; pytest testpaths=["services"]), requirements.txt raíz,
   conftest.py (inserta los 3 services/*/src en sys.path), data/.gitkeep.
2. Servicio auth: estructura + main + config + test_health (GET /health → 200 status ok).
3. Servicio inventory: ídem (SERVICE_NAME=inventory).
4. Servicio sales: ídem (SERVICE_NAME=sales).
5. Frontend: crear proyecto Vite (react-ts) en frontend/, instalar deps, crear theme.ts
   (paleta Lightdash de docs/ARCHITECTURE.md §9), client.ts, App con react-router y páginas
   placeholder (Login con tarjeta centrada; Admin y Empleado con texto "En construcción").
   Verificar npm run build.
6. start-all.ps1: valida que existen .venv y frontend/node_modules; abre 4 ventanas
   PowerShell: uvicorn auth.main:app --app-dir services/auth/src --port 8001 (ídem
   inventory 8002, sales 8003) y npm run dev en frontend/. Ventanas con -NoExit.

## Criterios de aceptación
1. .venv\Scripts\pytest services -q → 3 passed (uno por servicio).
2. .venv\Scripts\ruff check services → sin errores.
3. cd frontend ; npm run build → exitoso (incluye tsc).
4. Servicios levantados: GET /health responde 200 {"service": ..., "status": "ok"} en
   8001, 8002 y 8003.
5. npm run dev → la SPA carga en http://localhost:5173 con las rutas placeholder.
6. .\start-all.ps1 abre las 4 ventanas y todo responde.

## Fuera de alcance
- Login/JWT reales (F-003), tablas de datos, endpoints de dominio, semilla (F-002),
  diseño final del dashboard, README (F-013), commits (no hacer commit salvo orden expresa).

## Comandos de verificación
```
# desde la raíz, con .venv creado e instalado:
.venv\Scripts\ruff check services
.venv\Scripts\pytest services -q
cd frontend ; npm run build
# arranque manual de cada servicio:
.venv\Scripts\python -m uvicorn auth.main:app --app-dir services/auth/src --port 8001
.venv\Scripts\python -m uvicorn inventory.main:app --app-dir services/inventory/src --port 8002
.venv\Scripts\python -m uvicorn sales.main:app --app-dir services/sales/src --port 8003
Invoke-WebRequest http://localhost:8001/health | Select-Object -ExpandProperty Content
```
Setup inicial (si no existe .venv): python -m venv .venv ;
.venv\Scripts\pip install -r requirements.txt ; y cd frontend ; npm install.
