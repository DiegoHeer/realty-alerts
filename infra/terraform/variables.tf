variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

# --- Proxmox ---

variable "vm_configs" {
  description = "VM configurations for the k3s cluster"
  type = list(object({
    name   = string
    role   = string
    vcpus  = number
    memory = number
    disk   = number
    ip     = string
  }))
}

variable "proxmox_node" {
  description = "Proxmox node name"
  type        = string
  default     = "pve"
}

variable "gateway" {
  description = "Network gateway IP"
  type        = string
  default     = "10.0.0.1"
}

variable "ssh_public_key" {
  description = "SSH public key for cloud-init"
  type        = string
  default     = ""
}

variable "ssh_private_key_path" {
  description = "Path to SSH private key for provisioning"
  type        = string
  default     = "~/.ssh/id_ed25519"
}

# --- K8s Base ---

variable "metallb_ip_range" {
  description = "IP range for MetalLB LoadBalancer"
  type        = string
  default     = "10.0.0.200-10.0.0.250"
}

variable "letsencrypt_email" {
  description = "Email for Let's Encrypt certificate notifications"
  type        = string
  default     = ""
}

# --- Supabase ---

variable "supabase_jwt_secret" {
  description = "JWT secret for Supabase Auth"
  type        = string
  sensitive   = true
  default     = ""
}

variable "supabase_postgres_password" {
  description = "PostgreSQL password for Supabase"
  type        = string
  sensitive   = true
  default     = ""
}

# --- Application ---

variable "domain" {
  description = "Base domain for ingress"
  type        = string
  default     = "dev.local"
}

variable "api_image_tag" {
  description = "Docker image tag for the API"
  type        = string
  default     = "latest"
}

variable "scraper_image_tag" {
  description = "Docker image tag for the scraper"
  type        = string
  default     = "latest"
}

variable "web_image_tag" {
  description = "Docker image tag for the landing page"
  type        = string
  default     = "latest"
}
