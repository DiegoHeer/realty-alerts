output "server_ip" {
  description = "IP address of the k3s server node"
  value       = [for vm in proxmox_virtual_environment_vm.k3s_node : vm.initialization[0].ip_config[0].ipv4[0].address if contains(vm.tags, "server")][0]
}

output "agent_ips" {
  description = "IP addresses of k3s agent nodes"
  value       = [for vm in proxmox_virtual_environment_vm.k3s_node : vm.initialization[0].ip_config[0].ipv4[0].address if contains(vm.tags, "agent")]
}

output "all_ips" {
  description = "All VM IP addresses"
  value = {
    for name, vm in proxmox_virtual_environment_vm.k3s_node :
    name => vm.initialization[0].ip_config[0].ipv4[0].address
  }
}
