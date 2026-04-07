terraform {
  required_version = ">= 1.7"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.70"
    }
  }
}

module "proxmox_vms" {
  source = "./modules/proxmox-vm"

  environment = var.environment
  vm_configs  = var.vm_configs
}

module "k3s_cluster" {
  source = "./modules/k3s-cluster"

  environment = var.environment
  server_ip   = module.proxmox_vms.server_ip
  agent_ips   = module.proxmox_vms.agent_ips

  depends_on = [module.proxmox_vms]
}

module "k8s_base" {
  source = "./modules/k8s-base"

  environment = var.environment

  depends_on = [module.k3s_cluster]
}

module "supabase" {
  source = "./modules/supabase"

  environment = var.environment

  depends_on = [module.k8s_base]
}

module "monitoring" {
  source = "./modules/monitoring"

  environment = var.environment

  depends_on = [module.k8s_base]
}

module "k8s_app" {
  source = "./modules/k8s-app"

  environment   = var.environment
  api_image_tag = var.api_image_tag

  depends_on = [module.supabase]
}
