environment = "prod"

vm_configs = [
  {
    name   = "prod-k3s-server"
    role   = "server"
    vcpus  = 4
    memory = 8192
    disk   = 80
    ip     = "10.0.1.10"
  },
  {
    name   = "prod-k3s-agent-1"
    role   = "agent"
    vcpus  = 4
    memory = 16384
    disk   = 100
    ip     = "10.0.1.11"
  },
  {
    name   = "prod-k3s-agent-2"
    role   = "agent"
    vcpus  = 4
    memory = 16384
    disk   = 100
    ip     = "10.0.1.12"
  },
]
