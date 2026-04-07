output "app_namespace" {
  description = "Application namespace name"
  value       = kubernetes_namespace.app.metadata[0].name
}

output "monitoring_namespace" {
  description = "Monitoring namespace name"
  value       = kubernetes_namespace.monitoring.metadata[0].name
}

output "supabase_namespace" {
  description = "Supabase namespace name"
  value       = kubernetes_namespace.supabase.metadata[0].name
}

output "cluster_issuer_name" {
  description = "Name of the ClusterIssuer for TLS certificates"
  value       = var.environment == "prod" ? "letsencrypt" : "selfsigned"
}
