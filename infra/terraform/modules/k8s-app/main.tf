locals {
  namespace = var.namespace != "" ? var.namespace : "realty-${var.environment}"
  labels = {
    "app.kubernetes.io/managed-by" = "terraform"
    "environment"                  = var.environment
  }
}

# ============================================================
# Backend API
# ============================================================

resource "kubernetes_deployment" "api" {
  metadata {
    name      = "${var.environment}-realty-api"
    namespace = local.namespace
    labels    = merge(local.labels, { "app" = "realty-api" })
  }

  spec {
    replicas = var.api_replicas

    selector {
      match_labels = { "app" = "realty-api" }
    }

    template {
      metadata {
        labels = merge(local.labels, { "app" = "realty-api" })
        annotations = {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "8000"
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        container {
          name  = "api"
          image = "${var.ghcr_image_prefix}/realty-api:${var.api_image_tag}"

          port {
            container_port = 8000
          }

          env_from {
            secret_ref {
              name = "realty-api-secrets"
            }
          }

          env_from {
            config_map_ref {
              name = "realty-api-config"
            }
          }

          liveness_probe {
            http_get {
              path = "/healthz"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 20
          }

          readiness_probe {
            http_get {
              path = "/readyz"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 10
          }

          resources {
            requests = {
              cpu    = var.environment == "prod" ? "250m" : "100m"
              memory = var.environment == "prod" ? "256Mi" : "128Mi"
            }
            limits = {
              cpu    = "1000m"
              memory = "512Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "api" {
  metadata {
    name      = "realty-api"
    namespace = local.namespace
    labels    = merge(local.labels, { "app" = "realty-api" })
  }

  spec {
    selector = { "app" = "realty-api" }

    port {
      port        = 8000
      target_port = 8000
    }
  }
}

resource "kubernetes_config_map" "api_config" {
  metadata {
    name      = "realty-api-config"
    namespace = local.namespace
  }

  data = {
    API_LOG_LEVEL = var.environment == "prod" ? "info" : "debug"
    API_TIMEZONE  = "Europe/Amsterdam"
  }
}

# ============================================================
# Playwright Server (shared, for Funda scraping)
# ============================================================

resource "kubernetes_deployment" "playwright" {
  metadata {
    name      = "${var.environment}-playwright"
    namespace = local.namespace
    labels    = merge(local.labels, { "app" = "playwright-server" })
  }

  spec {
    replicas = 1

    selector {
      match_labels = { "app" = "playwright-server" }
    }

    template {
      metadata {
        labels = merge(local.labels, { "app" = "playwright-server" })
      }

      spec {
        container {
          name    = "playwright"
          image   = "mcr.microsoft.com/playwright:v1.53.0-noble"
          command = ["/bin/sh", "-c", "npx -y playwright@1.53.0 run-server --port 3000 --host 0.0.0.0"]

          port {
            container_port = 3000
          }

          resources {
            requests = {
              cpu    = "250m"
              memory = "512Mi"
            }
            limits = {
              cpu    = "1000m"
              memory = "1Gi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "playwright" {
  metadata {
    name      = "playwright-server"
    namespace = local.namespace
  }

  spec {
    selector = { "app" = "playwright-server" }

    port {
      port        = 3000
      target_port = 3000
    }
  }
}

# ============================================================
# Scraper CronJobs (one per website)
# ============================================================

locals {
  scraper_websites = {
    funda       = "0 */2 * * *"  # every 2 hours
    pararius    = "30 */2 * * *" # every 2 hours, offset 30min
    vastgoed_nl = "0 */3 * * *"  # every 3 hours
  }
}

resource "kubernetes_cron_job_v1" "scraper" {
  for_each = local.scraper_websites

  metadata {
    name      = "${var.environment}-scraper-${replace(each.key, "_", "-")}"
    namespace = local.namespace
    labels    = merge(local.labels, { "app" = "realty-scraper", "website" = each.key })
  }

  spec {
    schedule                      = each.value
    concurrency_policy            = "Forbid"
    successful_jobs_history_limit = 3
    failed_jobs_history_limit     = 3
    starting_deadline_seconds     = 120

    job_template {
      metadata {
        labels = merge(local.labels, { "app" = "realty-scraper", "website" = each.key })
      }

      spec {
        backoff_limit          = 2
        active_deadline_seconds = 600

        template {
          metadata {
            labels = merge(local.labels, { "app" = "realty-scraper", "website" = each.key })
          }

          spec {
            restart_policy = "Never"

            container {
              name  = "scraper"
              image = "${var.ghcr_image_prefix}/realty-scraper:${var.scraper_image_tag}"
              command = ["python", "-m", "scraper"]

              env {
                name  = "WEBSITE"
                value = each.key
              }

              env {
                name  = "BACKEND_API_URL"
                value = "http://realty-api.${local.namespace}.svc:8000"
              }

              env {
                name  = "BROWSER_URL"
                value = "ws://playwright-server.${local.namespace}.svc:3000"
              }

              env_from {
                secret_ref {
                  name = "realty-scraper-secrets"
                }
              }

              resources {
                requests = {
                  cpu    = "100m"
                  memory = "128Mi"
                }
                limits = {
                  cpu    = "500m"
                  memory = "256Mi"
                }
              }
            }
          }
        }
      }
    }
  }
}

# ============================================================
# Landing Page
# ============================================================

resource "kubernetes_deployment" "web" {
  metadata {
    name      = "${var.environment}-realty-web"
    namespace = local.namespace
    labels    = merge(local.labels, { "app" = "realty-web" })
  }

  spec {
    replicas = 1

    selector {
      match_labels = { "app" = "realty-web" }
    }

    template {
      metadata {
        labels = merge(local.labels, { "app" = "realty-web" })
      }

      spec {
        container {
          name  = "web"
          image = "${var.ghcr_image_prefix}/realty-web:${var.web_image_tag}"

          port {
            container_port = 80
          }

          resources {
            requests = {
              cpu    = "10m"
              memory = "32Mi"
            }
            limits = {
              cpu    = "100m"
              memory = "64Mi"
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "web" {
  metadata {
    name      = "realty-web"
    namespace = local.namespace
  }

  spec {
    selector = { "app" = "realty-web" }

    port {
      port        = 80
      target_port = 80
    }
  }
}

# ============================================================
# Traefik IngressRoute (API + Landing Page)
# ============================================================

resource "kubernetes_manifest" "ingress_api" {
  manifest = {
    apiVersion = "traefik.io/v1alpha1"
    kind       = "IngressRoute"
    metadata = {
      name      = "realty-api"
      namespace = local.namespace
      annotations = {
        "cert-manager.io/cluster-issuer" = var.cluster_issuer
      }
    }
    spec = {
      entryPoints = ["websecure"]
      routes = [
        {
          match = "Host(`api.${var.domain}`)"
          kind  = "Rule"
          services = [
            {
              name = "realty-api"
              port = 8000
            }
          ]
        }
      ]
      tls = {
        secretName = "realty-api-tls"
      }
    }
  }
}

resource "kubernetes_manifest" "ingress_web" {
  manifest = {
    apiVersion = "traefik.io/v1alpha1"
    kind       = "IngressRoute"
    metadata = {
      name      = "realty-web"
      namespace = local.namespace
      annotations = {
        "cert-manager.io/cluster-issuer" = var.cluster_issuer
      }
    }
    spec = {
      entryPoints = ["websecure"]
      routes = [
        {
          match = "Host(`${var.domain}`)"
          kind  = "Rule"
          services = [
            {
              name = "realty-web"
              port = 80
            }
          ]
        }
      ]
      tls = {
        secretName = "realty-web-tls"
      }
    }
  }
}
