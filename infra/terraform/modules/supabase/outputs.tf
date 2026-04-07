output "supabase_url" {
  description = "Internal Supabase Kong gateway URL"
  value       = "http://supabase-kong.${var.namespace}.svc.cluster.local:8000"
}

output "database_url" {
  description = "Internal PostgreSQL connection string (async)"
  value       = "postgresql+asyncpg://supabase_admin:${var.postgres_password}@supabase-db.${var.namespace}.svc.cluster.local:5432/postgres"
  sensitive   = true
}
