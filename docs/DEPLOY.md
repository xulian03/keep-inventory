# Despliegue de KeepInventory (Vagrant + Ansible)

Guía para levantar la aplicación desde cero en Windows, cumpliendo la fase de
despliegue: backend y frontend en servidores separados y acceso desde el cliente
Windows por nombre de dominio.

## Qué despliega

- **Backend — 192.168.56.10**: los 3 microservicios (auth :8001, inventory :8002,
  sales :8003) con sus BDs SQLite, servidos por systemd.
- **Frontend — 192.168.56.20**: nginx sirviendo la app React compilada y actuando
  de reverse proxy hacia el backend.
- **Dominio**: `http://keepinventory.local` (nginx enruta `/auth/*`, `/inventory/*`
  y `/sales/*` al microservicio correspondiente).

## Prerequisitos

- Windows con **VirtualBox** y **Vagrant** instalados.
- **WSL** (Ubuntu) con **Ansible**: `sudo apt install ansible` o `pip install ansible`.
- **Git** en Windows.

## Procedimiento (4 pasos)

1. En PowerShell, clonar el repositorio y entrar a la carpeta:
   `git clone https://github.com/xulian03/keep-inventory.git; cd keep-inventory`
2. Crear y arrancar las 2 VMs (la primera vez descarga la box `ubuntu/jammy64`):
   `vagrant up`. Esperar a que ambas queden `running` (`vagrant status`).
3. Desde WSL, en la misma carpeta clonada, aprovisionar con Ansible (tarda:
   dependencias de Python incluido scikit-learn, y build de npm):
   `ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i ansible/inventory.ini ansible/deploy.yml`
4. En Windows, como Administrador, mapear el dominio y abrir
   `http://keepinventory.local` en el navegador:
   `powershell -ExecutionPolicy Bypass -File scripts\add-hosts.ps1`

## Verificación manual (evidencia)

En el navegador: login con **admin@tienda.com / admin123** y ver el dashboard.
En PowerShell, los 3 comandos listos para copiar (salud por el dominio, login que
devuelve el token y catálogo con el token):

```powershell
Invoke-WebRequest http://keepinventory.local/sales/health | Select-Object -ExpandProperty Content
$login = Invoke-RestMethod -Method Post http://keepinventory.local/auth/auth/login -Body (@{email="admin@tienda.com";password="admin123"} | ConvertTo-Json) -ContentType "application/json"; $login.token
Invoke-RestMethod http://keepinventory.local/inventory/products -Headers @{Authorization="Bearer $($login.token)"}
```

## Credenciales demo

- admin@tienda.com / admin123 (Dueño/Admin)
- empleado@tienda.com / empleado123 (Empleado/Vendedor)
- vendedor2@tienda.com / vendedor123 (Empleado/Vendedor)

## Si algo falla

- Recrear todo desde cero: `vagrant destroy -f` y repetir los pasos.
- Entrar a una VM a revisar: `vagrant ssh backend` o `vagrant ssh frontend`.
- Apagar sin borrar: `vagrant halt`.
- Las BDs se regeneran con la semilla si borras los `.db` en `/opt/keepinventory` y
  re-corres el paso 3 (`ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i ansible/inventory.ini ansible/deploy.yml`).
- Si tras recrear las VMs sale "REMOTE HOST IDENTIFICATION HAS CHANGED", ejecutar
  `ssh-keygen -R 192.168.56.10` y `ssh-keygen -R 192.168.56.20`, y recordar
  `sudo apt install -y sshpass`.
