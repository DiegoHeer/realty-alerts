output "k3s_kubeconfig" {
  description = "Path to the k3s kubeconfig"
  value       = module.k3s_cluster.kubeconfig_path
  sensitive   = true
}

output "api_endpoint" {
  description = "API service endpoint"
  value       = module.k8s_app.api_endpoint
}
