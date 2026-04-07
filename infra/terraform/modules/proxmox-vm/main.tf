resource "proxmox_virtual_environment_vm" "k3s_node" {
  for_each = { for vm in var.vm_configs : vm.name => vm }

  name      = each.value.name
  node_name = var.proxmox_node
  on_boot   = true
  started   = true

  clone {
    vm_id = var.template_id
  }

  cpu {
    cores = each.value.vcpus
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = each.value.memory
  }

  disk {
    datastore_id = var.storage_pool
    size         = each.value.disk
    interface    = "scsi0"
  }

  network_device {
    bridge = "vmbr0"
  }

  initialization {
    ip_config {
      ipv4 {
        address = "${each.value.ip}/24"
        gateway = var.gateway
      }
    }

    dns {
      servers = [var.nameserver]
    }

    user_account {
      username = "ubuntu"
      keys     = var.ssh_public_key != "" ? [var.ssh_public_key] : []
    }
  }

  tags = [var.environment, each.value.role, "k3s"]

  lifecycle {
    ignore_changes = [initialization]
  }
}
