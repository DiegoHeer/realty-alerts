# --- VictoriaMetrics (single-node, Prometheus-compatible) ---

resource "helm_release" "victoria_metrics" {
  name       = "victoria-metrics"
  namespace  = var.namespace
  repository = "https://victoriametrics.github.io/helm-charts"
  chart      = "victoria-metrics-single"
  version    = var.victoria_metrics_version

  set {
    name  = "server.retentionPeriod"
    value = "${var.retention_days}d"
  }

  set {
    name  = "server.persistentVolume.storageClass"
    value = var.storage_class
  }

  set {
    name  = "server.persistentVolume.size"
    value = var.environment == "prod" ? "10Gi" : "2Gi"
  }

  set {
    name  = "server.resources.requests.memory"
    value = "256Mi"
  }

  set {
    name  = "server.resources.requests.cpu"
    value = "100m"
  }
}

# --- VictoriaLogs (lightweight log aggregation) ---

resource "helm_release" "victoria_logs" {
  name       = "victoria-logs"
  namespace  = var.namespace
  repository = "https://victoriametrics.github.io/helm-charts"
  chart      = "victoria-logs-single"
  version    = var.victoria_logs_version

  set {
    name  = "server.retentionPeriod"
    value = "${var.environment == "prod" ? var.retention_days : 3}d"
  }

  set {
    name  = "server.persistentVolume.storageClass"
    value = var.storage_class
  }

  set {
    name  = "server.persistentVolume.size"
    value = var.environment == "prod" ? "10Gi" : "2Gi"
  }
}

# --- Grafana Alloy (unified telemetry collector) ---

resource "helm_release" "alloy" {
  name       = "alloy"
  namespace  = var.namespace
  repository = "https://grafana.github.io/helm-charts"
  chart      = "alloy"
  version    = var.grafana_alloy_version

  values = [yamlencode({
    alloy = {
      configMap = {
        content = <<-EOT
          // Scrape k8s pods with prometheus.io annotations
          prometheus.scrape "pods" {
            targets    = discovery.kubernetes.pods.targets
            forward_to = [prometheus.remote_write.victoria.receiver]
          }

          discovery.kubernetes "pods" {
            role = "pod"
          }

          prometheus.remote_write "victoria" {
            endpoint {
              url = "http://victoria-metrics-server.${var.namespace}.svc:8428/api/v1/write"
            }
          }

          // Collect logs from all pods
          loki.source.kubernetes "pods" {
            targets    = discovery.kubernetes.pods.targets
            forward_to = [loki.write.victoria_logs.receiver]
          }

          loki.write "victoria_logs" {
            endpoint {
              url = "http://victoria-logs-server.${var.namespace}.svc:9428/insert/loki/api/v1/push"
            }
          }
        EOT
      }
    }
  })]
}

# --- Grafana (dashboards + alerting) ---

resource "helm_release" "grafana" {
  name       = "grafana"
  namespace  = var.namespace
  repository = "https://grafana.github.io/helm-charts"
  chart      = "grafana"
  version    = var.grafana_version

  set {
    name  = "persistence.enabled"
    value = "true"
  }

  set {
    name  = "persistence.storageClassName"
    value = var.storage_class
  }

  set {
    name  = "persistence.size"
    value = "1Gi"
  }

  set {
    name  = "resources.requests.memory"
    value = "128Mi"
  }

  set {
    name  = "resources.requests.cpu"
    value = "50m"
  }

  values = [yamlencode({
    datasources = {
      "datasources.yaml" = {
        apiVersion  = 1
        datasources = [
          {
            name      = "VictoriaMetrics"
            type      = "prometheus"
            url       = "http://victoria-metrics-server.${var.namespace}.svc:8428"
            isDefault = true
            access    = "proxy"
          },
          {
            name   = "VictoriaLogs"
            type   = "loki"
            url    = "http://victoria-logs-server.${var.namespace}.svc:9428"
            access = "proxy"
          },
        ]
      }
    }
  })]
}
