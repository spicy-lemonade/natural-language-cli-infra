terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Uncomment to use remote state in GCS
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "nlcli-wizard/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
