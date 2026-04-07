variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace for Supabase"
  type        = string
  default     = "supabase"
}

variable "supabase_chart_version" {
  description = "Supabase Helm chart version"
  type        = string
  default     = "0.2.0"
}

variable "jwt_secret" {
  description = "JWT secret for Supabase Auth (HS256)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "postgres_password" {
  description = "PostgreSQL password for Supabase"
  type        = string
  sensitive   = true
  default     = ""
}

variable "dashboard_enabled" {
  description = "Enable Supabase Studio dashboard"
  type        = bool
  default     = true
}

variable "storage_class" {
  description = "Storage class for persistent volumes"
  type        = string
  default     = "longhorn"
}
