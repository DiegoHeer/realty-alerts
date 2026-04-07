output "k3s_kubeconfig" {
  description = "Path to the k3s kubeconfig file"
  value       = module.k3s_cluster.kubeconfig_path
  sensitive   = true
}

output "k3s_server_url" {
  description = "k3s API server URL"
  value       = module.k3s_cluster.server_url
}

output "api_internal_endpoint" {
  description = "API service internal K8s endpoint"
  value       = module.k8s_app.api_endpoint
}

output "api_external_url" {
  description = "API external URL via ingress"
  value       = module.k8s_app.api_external_url
}

output "web_external_url" {
  description = "Landing page external URL"
  value       = module.k8s_app.web_external_url
}

output "supabase_url" {
  description = "Supabase internal URL"
  value       = module.supabase.supabase_url
}

output "grafana_url" {
  description = "Grafana internal URL"
  value       = module.monitoring.grafana_url
}

output "scraper_cronjobs" {
  description = "Deployed scraper CronJob names"
  value       = module.k8s_app.scraper_cronjobs
}

output "vm_ips" {
  description = "All VM IP addresses"
  value       = module.proxmox_vms.all_ips
}
