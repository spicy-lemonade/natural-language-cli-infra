# Firebase and Firestore Configuration

# Enable Firebase Management API
resource "google_project_service" "firebase" {
  project = var.project_id
  service = "firebase.googleapis.com"

  disable_on_destroy = false
}

# Enable Firestore API
resource "google_project_service" "firestore" {
  project = var.project_id
  service = "firestore.googleapis.com"

  disable_on_destroy = false
}

# Enable Firebase App Check API (required for Firebase)
resource "google_project_service" "firebaseappcheck" {
  project = var.project_id
  service = "firebaseappcheck.googleapis.com"

  disable_on_destroy = false
}

# Enable Identity Toolkit API (required for Firebase Auth)
resource "google_project_service" "identitytoolkit" {
  project = var.project_id
  service = "identitytoolkit.googleapis.com"

  disable_on_destroy = false
}

# Initialize Firebase project
resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.project_id

  depends_on = [
    google_project_service.firebase,
    google_project_service.firebaseappcheck,
    google_project_service.identitytoolkit,
  ]
}

# Create Firestore database in Native mode
resource "google_firestore_database" "zest_cli" {
  provider    = google-beta
  project     = var.project_id
  name        = "zest-cli"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [
    google_firebase_project.default,
    google_project_service.firestore,
  ]
}
