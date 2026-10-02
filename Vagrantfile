# Vagrantfile — F-011: define 2 VMs VirtualBox (backend y frontend) del despliegue.
# Solo crea las máquinas; el aprovisionamiento lo hace Ansible (carpeta ansible/).
# La red 192.168.56.x es la red host-only por defecto de VirtualBox.

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"

  # backend: 3 microservicios FastAPI + BDs -> 192.168.56.10, 2GB RAM / 2 vCPU.
  # frontend: nginx sirviendo el React compilado -> 192.168.56.20, 1GB RAM / 1 vCPU.
  vms = {
    "backend"  => { ip: "192.168.56.10", memory: 2048, cpus: 2 },
    "frontend" => { ip: "192.168.56.20", memory: 1024, cpus: 1 }
  }

  vms.each do |name, opts|
    config.vm.define name do |machine|
      machine.vm.hostname = name
      machine.vm.network "private_network", ip: opts[:ip]

      machine.vm.provider "virtualbox" do |vb|
        vb.memory = opts[:memory]
        vb.cpus = opts[:cpus]
      end
    end
  end
end
