variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be 'dev' or 'prod'."
  }
}

variable "vm_configs" {
  description = "VM configurations for the k3s cluster"
  type = list(object({
    name   = string
    role   = string # "server" or "agent"
    vcpus  = number
    memory = number # MB
    disk   = number # GB
    ip     = string
  }))
}

variable "api_image_tag" {
  description = "Docker image tag for the API service"
  type        = string
  default     = "latest"
}
