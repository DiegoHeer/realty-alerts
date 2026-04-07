variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace for the application"
  type        = string
  default     = ""
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

variable "api_replicas" {
  description = "Number of API pod replicas"
  type        = number
  default     = 1
}

variable "domain" {
  description = "Base domain for ingress (e.g. realtyalerts.nl or dev.local)"
  type        = string
  default     = "dev.local"
}

variable "cluster_issuer" {
  description = "cert-manager ClusterIssuer name for TLS"
  type        = string
  default     = "selfsigned"
}

variable "ghcr_image_prefix" {
  description = "Container registry prefix"
  type        = string
  default     = "ghcr.io/diegoheer"
}
