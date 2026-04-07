output "victoria_metrics_url" {
  description = "Internal VictoriaMetrics write endpoint"
  value       = "http://victoria-metrics-server.${var.namespace}.svc:8428"
}

output "grafana_url" {
  description = "Internal Grafana URL"
  value       = "http://grafana.${var.namespace}.svc:80"
}
