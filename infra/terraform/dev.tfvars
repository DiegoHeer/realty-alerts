environment = "dev"

# --- Proxmox VMs ---
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

# --- Network ---
gateway          = "10.0.0.1"
metallb_ip_range = "10.0.0.200-10.0.0.220"
domain           = "dev.local"

# --- Secrets (override via TF_VAR_ env vars or -var flag) ---
# supabase_jwt_secret        = ""
# supabase_postgres_password = ""
