resource "helm_release" "supabase" {
  name       = "supabase"
  namespace  = var.namespace
  repository = "https://supabase-community.github.io/supabase-kubernetes"
  chart      = "supabase"
  version    = var.supabase_chart_version

  # Disable PostgREST — FastAPI is the API layer
  set {
    name  = "rest.enabled"
    value = "false"
  }

  # Enable Realtime for live subscriptions
  set {
    name  = "realtime.enabled"
    value = "true"
  }

  # Auth (GoTrue)
  set {
    name  = "auth.enabled"
    value = "true"
  }

  # Studio dashboard
  set {
    name  = "studio.enabled"
    value = tostring(var.dashboard_enabled)
  }

  # PostgreSQL
  set {
    name  = "db.enabled"
    value = "true"
  }

  set {
    name  = "db.persistence.storageClass"
    value = var.storage_class
  }

  set {
    name  = "db.persistence.size"
    value = var.environment == "prod" ? "20Gi" : "5Gi"
  }

  # JWT secret
  set_sensitive {
    name  = "jwt.secret"
    value = var.jwt_secret
  }

  # Postgres password
  set_sensitive {
    name  = "db.password"
    value = var.postgres_password
  }
}
