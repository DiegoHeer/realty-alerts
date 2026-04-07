variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "vm_configs" {
  description = "List of VM configurations to create"
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
  description = "Proxmox node name to deploy VMs on"
  type        = string
  default     = "pve"
}

variable "template_id" {
  description = "VM template ID (cloud-init Ubuntu 24.04 image)"
  type        = number
  default     = 9000
}

variable "gateway" {
  description = "Network gateway IP"
  type        = string
  default     = "10.0.0.1"
}

variable "nameserver" {
  description = "DNS nameserver"
  type        = string
  default     = "1.1.1.1"
}

variable "ssh_public_key" {
  description = "SSH public key for cloud-init user access"
  type        = string
  default     = ""
}

variable "storage_pool" {
  description = "Proxmox storage pool for VM disks"
  type        = string
  default     = "local-lvm"
}
