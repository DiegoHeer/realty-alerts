environment = "prod"

# --- Proxmox VMs ---
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

# --- Network ---
gateway          = "10.0.1.1"
metallb_ip_range = "10.0.1.200-10.0.1.220"
domain           = "realtyalerts.nl"

# --- Let's Encrypt ---
letsencrypt_email = "admin@realtyalerts.nl"

# --- Secrets (override via TF_VAR_ env vars or -var flag) ---
# supabase_jwt_secret        = ""
# supabase_postgres_password = ""
