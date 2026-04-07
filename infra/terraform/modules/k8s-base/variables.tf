variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "metallb_ip_range" {
  description = "IP range for MetalLB LoadBalancer (e.g. 10.0.0.200-10.0.0.250)"
  type        = string
  default     = "10.0.0.200-10.0.0.250"
}

variable "letsencrypt_email" {
  description = "Email for Let's Encrypt certificate notifications"
  type        = string
  default     = ""
}

variable "cert_manager_version" {
  description = "cert-manager Helm chart version"
  type        = string
  default     = "1.16.3"
}

variable "longhorn_version" {
  description = "Longhorn Helm chart version"
  type        = string
  default     = "1.7.2"
}

variable "sealed_secrets_version" {
  description = "Sealed Secrets Helm chart version"
  type        = string
  default     = "2.16.2"
}

variable "metallb_version" {
  description = "MetalLB Helm chart version"
  type        = string
  default     = "0.14.9"
}
