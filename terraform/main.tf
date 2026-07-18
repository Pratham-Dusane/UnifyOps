# VPC Service Controls & Network Perimeter Configuration (Phase 9.3)
# Establishes network security perimeter for staging and production environments.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type        = string
  default     = "unifyops"
  description = "GCP Project ID"
}

variable "region" {
  type        = string
  default     = "asia-south1"
  description = "GCP region"
}

variable "access_policy_title" {
  type        = string
  default     = "UnifyOps Organization Access Policy"
}

variable "org_id" {
  type        = string
  default     = "123456789"
  description = "GCP Organization ID"
}

# 1. Access Policy under ACM
resource "google_access_context_manager_access_policy" "policy" {
  parent = "organizations/${var.org_id}"
  title  = var.access_policy_title
}

# 2. VPC Service Controls Service Perimeter (FR-9.3.1)
resource "google_access_context_manager_service_perimeter" "service_perimeter" {
  parent      = "accessPolicies/${google_access_context_manager_access_policy.policy.name}"
  name        = "accessPolicies/${google_access_context_manager_access_policy.policy.name}/servicePerimeters/unifyops_data_perimeter"
  title       = "UnifyOps Data Perimeter"
  description = "Hardened perimeter for Spanner, Firestore, and GCS data layers"

  status {
    # Resources protected inside the perimeter
    resources = [
      "projects/${var.project_id}"
    ]

    # Google Cloud APIs locked down inside the perimeter
    restricted_services = [
      "spanner.googleapis.com",
      "storage.googleapis.com",
      "firestore.googleapis.com"
    ]

    # Ingress policies: permit traffic from authorised developer networks or pipelines
    ingress_policies {
      ingress_from {
        identity_type = "ANY_IDENTITY"
        sources {
          access_level = google_access_context_manager_access_level.corp_network.name
        }
      }
      ingress_to {
        resources = ["*"]
        operations {
          service_name = "*"
          method_selectors {
            method = "*"
          }
        }
      }
    }

    # Egress policies: strictly limit exfiltration of data outside the perimeter
    egress_policies {
      egress_to {
        resources = ["*"]
        operations {
          service_name = "storage.googleapis.com"
          method_selectors {
            method = "google.storage.objects.get"
          }
        }
      }
      egress_from {
        identity_type = "ANY_SERVICE_ACCOUNT"
      }
    }
  }
}

# 3. Access Level definition restricting access to corporate networks (FR-9.3.2)
resource "google_access_context_manager_access_level" "corp_network" {
  parent = "accessPolicies/${google_access_context_manager_access_policy.policy.name}"
  name   = "accessPolicies/${google_access_context_manager_access_policy.policy.name}/accessLevels/corp_network"
  title  = "Corporate Network Range"

  basic {
    conditions {
      ip_subnets = [
        "203.0.113.0/24",  # Mock Plant Corporate Network Range
        "198.51.100.0/22"  # Staging VPN Egress range
      ]
    }
  }
}
