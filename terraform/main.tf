locals {
  bucket_suffix      = var.bucket_suffix != "" ? var.bucket_suffix : random_id.bucket_suffix[0].hex
  bucket_name_bronze = "nlcli-ml-training-bronze-${var.environment}-${local.bucket_suffix}"
  bucket_name_silver = "nlcli-ml-training-silver-${var.environment}-${local.bucket_suffix}"
  bucket_name_gold   = "nlcli-ml-training-gold-${var.environment}-${local.bucket_suffix}"
}

resource "random_id" "bucket_suffix" {
  count       = var.bucket_suffix == "" ? 1 : 0
  byte_length = 4
}

resource "google_storage_bucket" "nlcli_ml_training_bronze" {
  name          = local.bucket_name_bronze
  location      = var.region
  storage_class = "STANDARD"
  project       = var.project_id

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  dynamic "lifecycle_rule" {
    for_each = var.data_retention_days > 0 ? [1] : []
    content {
      condition {
        age = var.data_retention_days
      }
      action {
        type = "Delete"
      }
    }
  }

  dynamic "lifecycle_rule" {
    for_each = var.enable_versioning ? [1] : []
    content {
      condition {
        num_newer_versions = 3
        with_state         = "ARCHIVED"
      }
      action {
        type = "Delete"
      }
    }
  }

  labels = {
    environment  = var.environment
    project      = "nlcli-wizard"
    data_layer   = "bronze"
    architecture = "medallion"
    purpose      = "ml-training"
  }
}

resource "google_storage_bucket" "nlcli_ml_training_silver" {
  name          = local.bucket_name_silver
  location      = var.region
  storage_class = "STANDARD"
  project       = var.project_id

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  dynamic "lifecycle_rule" {
    for_each = var.data_retention_days > 0 ? [1] : []
    content {
      condition {
        age = var.data_retention_days
      }
      action {
        type = "Delete"
      }
    }
  }

  dynamic "lifecycle_rule" {
    for_each = var.enable_versioning ? [1] : []
    content {
      condition {
        num_newer_versions = 3
        with_state         = "ARCHIVED"
      }
      action {
        type = "Delete"
      }
    }
  }

  labels = {
    environment  = var.environment
    project      = "nlcli-wizard"
    data_layer   = "silver"
    architecture = "medallion"
    purpose      = "ml-training"
  }
}

resource "google_storage_bucket" "nlcli_ml_training_gold" {
  name          = local.bucket_name_gold
  location      = var.region
  storage_class = "STANDARD"
  project       = var.project_id

  uniform_bucket_level_access = true

  versioning {
    enabled = var.enable_versioning
  }

  dynamic "lifecycle_rule" {
    for_each = var.data_retention_days > 0 ? [1] : []
    content {
      condition {
        age = var.data_retention_days
      }
      action {
        type = "Delete"
      }
    }
  }

  dynamic "lifecycle_rule" {
    for_each = var.enable_versioning ? [1] : []
    content {
      condition {
        num_newer_versions = 3
        with_state         = "ARCHIVED"
      }
      action {
        type = "Delete"
      }
    }
  }

  labels = {
    environment  = var.environment
    project      = "nlcli-wizard"
    data_layer   = "gold"
    architecture = "medallion"
    purpose      = "ml-training"
  }
}
