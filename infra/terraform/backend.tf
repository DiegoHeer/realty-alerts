terraform {
  backend "s3" {
    # Garage S3-compatible backend
    # Configure via environment or -backend-config flags:
    #   bucket         = "terraform-state"
    #   key            = "realty-alerts/terraform.tfstate"
    #   region         = "garage"
    #   endpoint       = "https://garage.local:3900"
    #   skip_credentials_validation = true
    #   skip_metadata_api_check     = true
    #   skip_region_validation      = true
    #   force_path_style            = true
  }
}
