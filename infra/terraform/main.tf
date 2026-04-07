terraform {
  required_version = ">= 1.7"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.70"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.35"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.17"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}

# ============================================================
# Layer 1: Proxmox VMs
# ============================================================

module "proxmox_vms" {
  source = "./modules/proxmox-vm"

  environment    = var.environment
  vm_configs     = var.vm_configs
  proxmox_node   = var.proxmox_node
  ssh_public_key = var.ssh_public_key
  gateway        = var.gateway
}

# ============================================================
# Layer 2: k3s Cluster Bootstrap
# ============================================================

module "k3s_cluster" {
  source = "./modules/k3s-cluster"

  environment          = var.environment
  server_ip            = module.proxmox_vms.server_ip
  agent_ips            = module.proxmox_vms.agent_ips
  ssh_private_key_path = var.ssh_private_key_path

  depends_on = [module.proxmox_vms]
}

# ============================================================
# Layer 3: K8s Base Resources
# ============================================================

module "k8s_base" {
  source = "./modules/k8s-base"

  environment      = var.environment
  metallb_ip_range = var.metallb_ip_range
  letsencrypt_email = var.letsencrypt_email

  depends_on = [module.k3s_cluster]
}

# ============================================================
# Layer 4a: Supabase
# ============================================================

module "supabase" {
  source = "./modules/supabase"

  environment       = var.environment
  jwt_secret        = var.supabase_jwt_secret
  postgres_password = var.supabase_postgres_password

  depends_on = [module.k8s_base]
}

# ============================================================
# Layer 4b: Monitoring (parallel with Supabase)
# ============================================================

module "monitoring" {
  source = "./modules/monitoring"

  environment = var.environment

  depends_on = [module.k8s_base]
}

# ============================================================
# Layer 5: Application Workloads
# ============================================================

module "k8s_app" {
  source = "./modules/k8s-app"

  environment       = var.environment
  namespace         = module.k8s_base.app_namespace
  api_image_tag     = var.api_image_tag
  scraper_image_tag = var.scraper_image_tag
  web_image_tag     = var.web_image_tag
  api_replicas      = var.environment == "prod" ? 2 : 1
  domain            = var.domain
  cluster_issuer    = module.k8s_base.cluster_issuer_name

  depends_on = [module.supabase]
}
