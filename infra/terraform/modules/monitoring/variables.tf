variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace for monitoring"
  type        = string
  default     = "monitoring"
}

variable "victoria_metrics_version" {
  description = "VictoriaMetrics single-node Helm chart version"
  type        = string
  default     = "0.14.3"
}

variable "grafana_alloy_version" {
  description = "Grafana Alloy Helm chart version"
  type        = string
  default     = "0.12.0"
}

variable "grafana_version" {
  description = "Grafana Helm chart version"
  type        = string
  default     = "8.8.2"
}

variable "victoria_logs_version" {
  description = "VictoriaLogs Helm chart version"
  type        = string
  default     = "0.9.1"
}

variable "retention_days" {
  description = "Metrics retention period in days"
  type        = number
  default     = 15
}

variable "storage_class" {
  description = "Storage class for persistent volumes"
  type        = string
  default     = "longhorn"
}
