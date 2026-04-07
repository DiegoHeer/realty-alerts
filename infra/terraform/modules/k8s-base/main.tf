# --- Namespaces ---

resource "kubernetes_namespace" "app" {
  metadata {
    name = "realty-${var.environment}"
    labels = {
      environment = var.environment
    }
  }
}

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

resource "kubernetes_namespace" "supabase" {
  metadata {
    name = "supabase"
  }
}

# --- cert-manager ---

resource "helm_release" "cert_manager" {
  name             = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  version          = var.cert_manager_version

  set {
    name  = "crds.enabled"
    value = "true"
  }
}

# ClusterIssuer for Let's Encrypt (prod) or self-signed (dev)
resource "kubernetes_manifest" "cluster_issuer" {
  depends_on = [helm_release.cert_manager]

  manifest = var.environment == "prod" ? {
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {
      name = "letsencrypt"
    }
    spec = {
      acme = {
        server = "https://acme-v02.api.letsencrypt.org/directory"
        email  = var.letsencrypt_email
        privateKeySecretRef = {
          name = "letsencrypt-account-key"
        }
        solvers = [{
          http01 = {
            ingress = {
              class = "traefik"
            }
          }
        }]
      }
    }
    } : {
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {
      name = "selfsigned"
    }
    spec = {
      selfSigned = {}
    }
  }
}

# --- MetalLB ---

resource "helm_release" "metallb" {
  name             = "metallb"
  namespace        = "metallb-system"
  create_namespace = true
  repository       = "https://metallb.github.io/metallb"
  chart            = "metallb"
  version          = var.metallb_version
}

resource "kubernetes_manifest" "metallb_ip_pool" {
  depends_on = [helm_release.metallb]

  manifest = {
    apiVersion = "metallb.io/v1beta1"
    kind       = "IPAddressPool"
    metadata = {
      name      = "${var.environment}-pool"
      namespace = "metallb-system"
    }
    spec = {
      addresses = [var.metallb_ip_range]
    }
  }
}

resource "kubernetes_manifest" "metallb_l2_advertisement" {
  depends_on = [helm_release.metallb]

  manifest = {
    apiVersion = "metallb.io/v1beta1"
    kind       = "L2Advertisement"
    metadata = {
      name      = "${var.environment}-l2"
      namespace = "metallb-system"
    }
    spec = {
      ipAddressPools = ["${var.environment}-pool"]
    }
  }
}

# --- Longhorn (distributed storage) ---

resource "helm_release" "longhorn" {
  name             = "longhorn"
  namespace        = "longhorn-system"
  create_namespace = true
  repository       = "https://charts.longhorn.io"
  chart            = "longhorn"
  version          = var.longhorn_version

  set {
    name  = "defaultSettings.defaultReplicaCount"
    value = var.environment == "prod" ? "2" : "1"
  }
}

# --- Sealed Secrets ---

resource "helm_release" "sealed_secrets" {
  name             = "sealed-secrets"
  namespace        = "kube-system"
  repository       = "https://bitnami-labs.github.io/sealed-secrets"
  chart            = "sealed-secrets"
  version          = var.sealed_secrets_version
}
