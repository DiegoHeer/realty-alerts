variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "server_ip" {
  description = "IP address of the k3s server node (from proxmox-vm module)"
  type        = string
}

variable "agent_ips" {
  description = "IP addresses of k3s agent nodes (from proxmox-vm module)"
  type        = list(string)
}

variable "ssh_user" {
  description = "SSH user for remote provisioning"
  type        = string
  default     = "ubuntu"
}

variable "ssh_private_key_path" {
  description = "Path to the SSH private key for provisioning"
  type        = string
  default     = "~/.ssh/id_ed25519"
}

variable "k3s_version" {
  description = "k3s version to install"
  type        = string
  default     = "v1.31.4+k3s1"
}

variable "cluster_cidr" {
  description = "Pod CIDR for the k3s cluster"
  type        = string
  default     = "10.42.0.0/16"
}

variable "service_cidr" {
  description = "Service CIDR for the k3s cluster"
  type        = string
  default     = "10.43.0.0/16"
}
