# add-hosts.ps1
# Mapea el dominio del despliegue (keepinventory.local) a la IP de la VM frontend
# (192.168.56.20) en el archivo hosts de Windows, para abrir la app por nombre de
# dominio. Debe ejecutarse como Administrador. Es idempotente: si la entrada ya
# existe no la duplica.

# Verificar que la consola se está ejecutando como Administrador.
$esAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $esAdmin) {
    Write-Host "Este script requiere permisos de Administrador. Ejecútalo de nuevo como Administrador."
    exit 1
}

$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
$entrada = "192.168.56.20 keepinventory.local"

if (Select-String -Path $hosts -SimpleMatch $entrada -Quiet) {
    Write-Host "La entrada ya existe en $hosts; no se modifica."
}
else {
    Add-Content -Path $hosts -Value $entrada
    Write-Host "Entrada agregada a $hosts."
}

Write-Host "Listo: http://keepinventory.local ahora apunta a la VM frontend (192.168.56.20)."
