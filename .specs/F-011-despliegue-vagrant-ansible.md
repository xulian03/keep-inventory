# F-011 — Despliegue en 2 servidores con Vagrant + Ansible (VirtualBox) — versión mínima

## Objetivo
2 VMs Ubuntu 22.04 (Vagrant + VirtualBox): backend (3 microservicios + BDs) y
frontend (nginx), acceso desde Windows vía http://keepinventory.local.

## Decisiones
- VMs: backend 192.168.56.10 (2GB/2vCPU), frontend 192.168.56.20 (1GB/1vCPU),
  ubuntu/jammy64. Vagrant SOLO crea las VMs. Ansible corre desde WSL.
- TODO Ansible en UN solo playbook: ansible/deploy.yml con 2 plays (hosts inline
  por IP con ansible_user=vagrant, ansible_password/become_password=vagrant,
  python3) + ansible/ansible.cfg (host_key_checking=False). Sin inventory,
  sin playbooks separados, sin roles.
- nginx: root=/opt/keepinventory/frontend/dist, reverse proxy /auth/*→:8001/*,
  /inventory/*→:8002/*, /sales/*→:8003/* (quita el primer segmento).
- Frontend compilado en la VM con VITE_{AUTH,INVENTORY,SALES}_URL =
  http://keepinventory.local/{auth,inventory,sales}; CORS: FRONTEND_URL=
  http://keepinventory.local en las 3 units.
- Copia de código a /opt/keepinventory (services/, scripts/seed.py y lo que
  importe, data/CSV, requirements.txt, frontend/). BDs en /opt/keepinventory.
- Semilla idempotente: solo corre si falta auth.db (creates).

## Archivos
- NUEVOS: ansible/ansible.cfg, ansible/deploy.yml, scripts/add-hosts.ps1,
  docs/DEPLOY.md.
- YA HECHO (paso 1): Vagrantfile, .gitignore (.vagrant/, *.retry, .agents/,
  skills-lock.json).

## Pasos atómicos
2. ansible/ansible.cfg + ansible/deploy.yml:
   - Play backend: apt python3-venv/pip; copia de código; venv + pip install
     -r requirements.txt; seed (creates=auth.db) con cwd=/opt/keepinventory y
     AUTH_DB/INVENTORY_DB/SALES_DB=/opt/keepinventory/*.db; 1 task de units
     systemd (loop de 3 servicios: uvicorn 0.0.0.0:800{1,2,3}, Environment
     FRONTEND_URL y las 3 BDs) + enable/start.
   - Play frontend: swapfile 2GB (build); Node 20 (NodeSource); copia
     frontend/; npm ci; npm run build con las VITE_*; nginx (1 site con
     server_name keepinventory.local, root dist y los 3 proxy_pass); enable
     site + reload.
3. scripts/add-hosts.ps1 (eleva a admin y añade "192.168.56.20
   keepinventory.local" al hosts de Windows, idempotente) y docs/DEPLOY.md
   (prerequisitos, 4 comandos del compañero: vagrant up, ansible-playbook
   ansible/deploy.yml desde WSL, add-hosts.ps1, abrir navegador; verificación
   manual: login admin@tienda.com y 3 Invoke-WebRequest de salud por el
   dominio). Sin smoke-test.ps1.

## Criterios de aceptación
- YAML válido (python yaml.safe_load); ruff/pytest siguen verdes; npm run build
  local con las VITE_* compila (prueba del paso 2).
- Sin VMs en este equipo (las prueba el compañero según DEPLOY.md).

## Fuera de alcance
Ejecutar VMs aquí; DNS real; HTTPS; smoke-test.ps1; inventario/roles Ansible;
README general (F-010).
