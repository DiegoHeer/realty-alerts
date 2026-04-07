output "api_endpoint" {
  description = "API service internal endpoint"
  value       = "http://realty-api.${local.namespace}.svc:8000"
}

output "api_external_url" {
  description = "API external URL via ingress"
  value       = "https://api.${var.domain}"
}

output "web_external_url" {
  description = "Landing page external URL via ingress"
  value       = "https://${var.domain}"
}

output "scraper_cronjobs" {
  description = "List of scraper CronJob names"
  value       = [for k, v in kubernetes_cron_job_v1.scraper : v.metadata[0].name]
}
