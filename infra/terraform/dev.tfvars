environment = "dev"

vm_configs = [
  {
    name   = "dev-k3s-server"
    role   = "server"
    vcpus  = 4
    memory = 8192
    disk   = 50
    ip     = "10.0.0.10"
  },
  {
    name   = "dev-k3s-agent-1"
    role   = "agent"
    vcpus  = 4
    memory = 8192
    disk   = 50
    ip     = "10.0.0.11"
  },
]
