# Strip the /24 CIDR suffix from IPs for SSH connections
locals {
  server_host = split("/", var.server_ip)[0]
  agent_hosts = [for ip in var.agent_ips : split("/", ip)[0]]
}

# --- k3s Server ---

resource "null_resource" "k3s_server" {
  connection {
    type        = "ssh"
    host        = local.server_host
    user        = var.ssh_user
    private_key = file(pathexpand(var.ssh_private_key_path))
  }

  provisioner "remote-exec" {
    inline = [
      "curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=${var.k3s_version} sh -s - server \\",
      "  --cluster-cidr=${var.cluster_cidr} \\",
      "  --service-cidr=${var.service_cidr} \\",
      "  --disable=servicelb \\",
      "  --write-kubeconfig-mode=644 \\",
      "  --tls-san=${local.server_host}",
    ]
  }
}

# Retrieve the node token for agents to join
data "external" "k3s_token" {
  depends_on = [null_resource.k3s_server]

  program = [
    "ssh", "-o", "StrictHostKeyChecking=no",
    "-i", pathexpand(var.ssh_private_key_path),
    "${var.ssh_user}@${local.server_host}",
    "echo", "{\\\"token\\\":\\\"$(sudo cat /var/lib/rancher/k3s/server/node-token)\\\"}"
  ]
}

# Retrieve kubeconfig
data "external" "kubeconfig" {
  depends_on = [null_resource.k3s_server]

  program = [
    "ssh", "-o", "StrictHostKeyChecking=no",
    "-i", pathexpand(var.ssh_private_key_path),
    "${var.ssh_user}@${local.server_host}",
    "echo", "{\\\"kubeconfig\\\":\\\"$(sudo cat /etc/rancher/k3s/k3s.yaml | base64 -w0)\\\"}"
  ]
}

# Write kubeconfig locally
resource "local_file" "kubeconfig" {
  content = replace(
    base64decode(data.external.kubeconfig.result["kubeconfig"]),
    "127.0.0.1",
    local.server_host
  )
  filename        = pathexpand("~/.kube/${var.environment}-k3s.yaml")
  file_permission = "0600"
}

# --- k3s Agents ---

resource "null_resource" "k3s_agent" {
  for_each = toset(local.agent_hosts)

  depends_on = [null_resource.k3s_server]

  connection {
    type        = "ssh"
    host        = each.value
    user        = var.ssh_user
    private_key = file(pathexpand(var.ssh_private_key_path))
  }

  provisioner "remote-exec" {
    inline = [
      "curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=${var.k3s_version} K3S_URL=https://${local.server_host}:6443 K3S_TOKEN=${data.external.k3s_token.result["token"]} sh -s -",
    ]
  }
}
