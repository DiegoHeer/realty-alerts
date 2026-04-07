provider "proxmox" {
  # Configured via environment variables:
  # PROXMOX_VE_ENDPOINT, PROXMOX_VE_USERNAME, PROXMOX_VE_PASSWORD
}

provider "kubernetes" {
  config_path = module.k3s_cluster.kubeconfig_path
}

provider "helm" {
  kubernetes {
    config_path = module.k3s_cluster.kubeconfig_path
  }
}
