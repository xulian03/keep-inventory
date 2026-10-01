<#
.SYNOPSIS
    Levanta los 3 microservicios (auth :8001, inventory :8002, sales :8003) y el frontend
    (:5173), cada uno en su propia ventana de PowerShell (-NoExit).
#>
$ErrorActionPreference = "Stop"

if (-not (Test-Path .venv)) {
    Write-Host "ERROR: no existe la carpeta .venv/. Ejecuta el setup de AGENTS.md:" -ForegroundColor Red
    Write-Host "  python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path frontend\node_modules)) {
    Write-Host "ERROR: no existe frontend/node_modules/. Ejecuta el setup de AGENTS.md:" -ForegroundColor Red
    Write-Host "  cd frontend ; npm install"
    exit 1
}

Write-Host "Abriendo 4 ventanas: auth=:8001, inventory=:8002, sales=:8003, frontend=:5173 ..."

# Servicios backend (uvicorn, cada uno con su paquete y su BD)
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", ".venv\Scripts\python -m uvicorn auth.main:app --app-dir services/auth/src --port 8001"
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", ".venv\Scripts\python -m uvicorn inventory.main:app --app-dir services/inventory/src --port 8002"
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", ".venv\Scripts\python -m uvicorn sales.main:app --app-dir services/sales/src --port 8003"

# Frontend (Vite dev server)
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Start-Sleep -Seconds 4
Write-Host ""
Write-Host "Todo arrancando. URLs:"
Write-Host "  Frontend:        http://localhost:5173"
Write-Host "  Auth /docs:      http://localhost:8001/docs"
Write-Host "  Inventory /docs: http://localhost:8002/docs"
Write-Host "  Sales /docs:     http://localhost:8003/docs"
