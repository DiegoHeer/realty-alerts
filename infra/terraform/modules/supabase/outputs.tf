output "supabase_url" {
  description = "Internal Supabase Kong gateway URL"
  value       = "http://supabase-kong.${var.namespace}.svc.cluster.local:8000"
}
