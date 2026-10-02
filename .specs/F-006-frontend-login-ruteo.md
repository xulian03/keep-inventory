# F-006 — Frontend: login y ruteo (layout por rol estilo Lightdash)

## Objetivo
Login funcional contra auth (:8001) con token en localStorage, redirect por rol
(admin → /admin, empleado → /empleado), guardas de ruta, sesión persistente al recargar
(GET /auth/me) y layout Lightdash (AppBar + Tabs por rol, §9) con paneles placeholder
que F-007..F-009 rellenarán. Sin cambios de backend.

## Contratos consumidos (F-003, sin cambios)
- POST /auth/login {email, password} → 200 {token, user{id, name, email, role}} | 401.
- GET /auth/me (Bearer) → 200 {id, name, email, role} | 401. role ∈ {admin, empleado}.

## Decisiones (marcadas para veto en revisión)
- Pestañas completas por rol desde ya, con paneles "en construcción" por pestaña:
  /admin → Resumen | Inventario | Predicciones | Órdenes de compra | Ventas;
  /empleado → Registrar venta | Recibir mercancía | Catálogo (§9).
  F-007..F-009 solo sustituyen paneles.
- Al montar la app: si hay token → GET /auth/me; 401/vacío → limpiar storage y /login.
- Login muestra credenciales demo (texto secundario) para facilitar la demo.
- Pestaña activa en estado local del layout (sin sync con URL).

## Archivos afectados
- Nuevos: frontend/src/auth/AuthContext.tsx (AuthProvider + useAuth: login, logout,
  token, user, ready), frontend/src/components/RequireRole.tsx (guarda por rol),
  frontend/src/components/AppLayout.tsx (AppBar + Tabs + paneles hijos),
  frontend/src/pages/Login.tsx, frontend/src/pages/Admin.tsx, frontend/src/pages/Empleado.tsx.
- Editar: frontend/src/App.tsx (AuthProvider, RequireRole, rutas reales /login /admin
  /empleado; elimina placeholders).
- Sin tocar: backend, api/client.ts, theme.ts, main.tsx.

## Pasos atómicos
1. AuthContext.tsx: tipos User/LoginResponse; login() → POST /auth/login (apiFetch,
   AUTH_URL), guarda token+user en localStorage; logout() limpia; restauración al
   montar con GET /auth/me (ready=false mientras valida).
2. App.tsx: AuthProvider; RequireRole (sin sesión → /login; rol incorrecto → home del
   rol); rutas: / → redirect, /login (público), /admin (admin), /empleado (empleado).
3. Login.tsx: formulario controlado email/password, submit → login() → redirect por
   rol, 401 → Alert "Credenciales inválidas", credenciales demo visibles; tarjeta
  blanca Lightdash centrada.
4. AppLayout.tsx + Admin.tsx + Empleado.tsx: AppBar (marca KeepInventory, nombre+rol
   del usuario, botón "Cerrar sesión"), Tabs por rol (§9), cada pestaña un panel
   placeholder con su título; fondo #F7F8FA.
5. Verificación completa: lint, build y smoke manual con los 3 usuarios demo.

## Criterios de aceptación
- cd frontend: npm run lint limpio; npm run build OK.
- Con servicios + semilla (.\start-all.ps1), en http://localhost:5173:
  - admin@tienda.com/admin123 → /admin (5 pestañas); empleado@tienda.com/empleado123
    y vendedor2@tienda.com/vendedor123 → /empleado (3 pestañas).
  - Credenciales inválidas → mensaje visible, sin redirect.
  - Recargar en /admin o /empleado mantiene sesión y ruta; "Cerrar sesión" → /login y
    al volver exige login; sin token, /admin y /empleado redirigen a /login.
  - Empleado autenticado que abre /admin es redirigido a /empleado (y viceversa).
- Backend intacto: ruff + pytest verdes (sin cambios esperados).

## Fuera de alcance
- Contenido real de pestañas (F-007 dashboard, F-008 decisión, F-009 empleado),
  llamadas a inventory/sales, manejo de 401 por expiración en caliente (solo al
  arrancar), tests unitarios de frontend (no hay runner), remember-me, cambio de
  contraseña, /auth/users, DataGrid/Recharts (llegan con F-007/F-008).

## Comandos de verificación
- cd frontend ; npm run lint ; npm run build
- .\start-all.ps1 ; navegador en http://localhost:5173 (escenarios de arriba).
- Opcional tras terminar: .venv\Scripts\ruff check services ; .venv\Scripts\pytest -q
