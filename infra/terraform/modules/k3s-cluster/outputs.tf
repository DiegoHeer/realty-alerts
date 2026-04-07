output "kubeconfig_path" {
  description = "Path to the generated kubeconfig file"
  value       = local_file.kubeconfig.filename
}

output "server_url" {
  description = "k3s API server URL"
  value       = "https://${local.server_host}:6443"
}

output "node_token" {
  description = "k3s node token for joining agents"
  value       = data.external.k3s_token.result["token"]
  sensitive   = true
}
