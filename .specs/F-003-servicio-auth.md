# Spec F-003 — Servicio Auth (login JWT + RBAC compartida)

## Objetivo
Auth emite y valida JWT por rol (ARCH §3, §5.1, §6.1): POST /auth/login devuelve
{token, user}; GET /auth/me valida el Bearer y devuelve los datos del usuario; y una
util de RBAC (create/decode + dependencia require_roles) queda disponible en los
TRES servicios (copiada, cada una con su config) para que F-004/F-006 solo la usen.

Decisiones de usuario (2026-10-01): GET/POST /auth/users queda FUERA de F-003;
rbac.py se copia a auth, inventory y sales (los servicios arrancan con --app-dir
propio y no pueden importar el paquete de auth).

## Archivos afectados
- Nuevos services/auth/src/auth/: rbac.py, schemas.py, routers/__init__.py,
  routers/auth.py.
- Actualizar services/auth/src/auth/main.py: incluir el router (CORS y /health intactos).
- Nuevos services/inventory/src/inventory/rbac.py y services/sales/src/sales/rbac.py:
  copia idéntica de auth salvo el import de su propio config (JWT_SECRET ya existe en
  los 3 config.py).
- Nuevos tests: services/auth/tests/test_auth.py; services/inventory/tests/test_rbac.py;
  services/sales/tests/test_rbac.py.

## Detalles concretos
- JWT HS256 con JWT_SECRET y JWT_EXPIRES_HOURS (24) del config. Claims: sub (str del
  id de usuario — PyJWT >=2.10 exige sub string), role, name, exp (ahora + 24 h).
- rbac.py expone: create_access_token(user_id, role, name) -> str;
  decode_token(token) -> dict (propaga jwt.InvalidTokenError, incl. expiración);
  get_current_user (dependencia HTTPBearer → {id, role, name}; 401 sin token o
  inválido/expirado); require_roles(*roles) (403 si role no permitido).
- POST /auth/login: {email, password} → 200 {token, user{id, name, email, role}};
  401 sin distinguir email desconocido vs contraseña errónea. Busca User por email y
  valida con security.verify_password.
- GET /auth/me: Bearer → busca el usuario por id (sub) en auth.db y devuelve
  {id, name, email, role}; 401 si el token es inválido/expirado o el usuario ya no existe.
- routers/auth.py define su dependencia get_session sobre db.get_engine()/
  get_session_factory() (respeta AUTH_DB redirigible por env para tests).

## Pasos atómicos
1. auth rbac.py (funciones y dependencias de arriba).
2. auth schemas.py: LoginRequest, UserPublic, LoginResponse (pydantic).
3. auth routers/auth.py: get_session + POST /auth/login + GET /auth/me (APIRouter
   prefix "/auth"); main.py lo incluye.
4. Copiar rbac.py a inventory y sales (solo cambia el import del config propio).
5. tests auth (auth.db temporal vía env AUTH_DB + create_all + 2 usuarios con
   hash_password: admin y empleado): login ok (token decodifica con el secreto y
   claims correctos, exp ≈ +24 h), password malo → 401, email desconocido → 401;
   /auth/me ok / sin token / token basura / token firmado con otro secreto /
   token expirado (fabricado con exp pasado) → 401; require_roles("admin") en una
   app dummy de test: admin 200, empleado 403, sin token 401.
6. tests inventory/sales (test_rbac.py): roundtrip create/decode con su config y
   require_roles 403 con rol contrario (app dummy), sin BD.

## Criterios de aceptación
1. Con auth.db sembrada y el servicio arrancado: POST /auth/login con
   admin@tienda.com/admin123 y empleado@tienda.com/empleado123 → 200 con token y
   user.role correcto; contraseña errónea → 401.
2. GET /auth/me con Bearer válido → 200 {id, name, email, role}; sin token,
   inválido o expirado → 401.
3. El token es HS256, verifica con el secreto compartido y trae sub/role/name/exp.
4. require_roles rechaza con 403 el rol no permitido (verificado por test en los
   3 servicios).
5. .venv\Scripts\pytest -q → todo verde (services + scripts/tests).
6. .venv\Scripts\ruff check services scripts → sin errores.
7. /health sigue OK y /docs de auth muestra login y me.

## Fuera de alcance
GET/POST /auth/users (decisión del usuario), logout/refresh de token, aplicar RBAC a
endpoints de inventory/sales (F-004/F-006), frontend (F-009), tocar seed.py o
ARCHITECTURE.md, hashear contraseñas nuevas (el hashing ya existe de F-002).

## Comandos de verificación
```
.venv\Scripts\pytest -q
.venv\Scripts\ruff check services scripts
# en vivo (requiere auth.db sembrada y .env opcional):
.venv\Scripts\python -m uvicorn auth.main:app --app-dir services/auth/src --port 8001
# otra terminal:
$t = (Invoke-RestMethod -Method Post http://localhost:8001/auth/login -ContentType "application/json" -Body '{"email":"admin@tienda.com","password":"admin123"}').token
Invoke-RestMethod http://localhost:8001/auth/me -Headers @{Authorization="Bearer $t"}
```
