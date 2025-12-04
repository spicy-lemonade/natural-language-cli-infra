# IAM Groups and Permissions

# Admin group
resource "google_project_iam_member" "admin_group" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "user:ciaranobrienmusic@gmail.com"
}

# ML Engineers group - Editor access at project level
resource "google_project_iam_member" "ml_engineers_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "group:spicy-lemonage-nl-cli-ml-engineers@googlegroups.com"
}
