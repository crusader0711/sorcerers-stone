# AWS Foundation — The Sorcerer's Stone
# Ref: .kiro/specs/phase-1-architecture/tasks.md Task 1.8
#
# Provider: AWS
# Resources: S3 bucket (backup target) + scoped IAM user
# Apply: terraform init && terraform plan && terraform apply
#
# Prerequisites:
#   - AWS CLI configured with an admin-level profile (NOT the backup user)
#   - terraform >= 1.7
#   - Run from: infra/terraform/

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
  # Optional: store state in S3 once the bucket exists
  # backend "s3" {
  #   bucket = "ofs-sorcerers-stone-backups"
  #   key    = "terraform/state"
  #   region = var.aws_region
  # }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 bucket name for encrypted backups"
  type        = string
  default     = "ofs-sorcerers-stone-backups"
}

variable "backup_prefix" {
  description = "S3 key prefix for backup objects"
  type        = string
  default     = "sorcerers-stone"
}

variable "iam_username" {
  description = "IAM user name for the backup agent"
  type        = string
  default     = "ss-backup-agent"
}

# ── S3 Bucket ─────────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "backups" {
  bucket = var.bucket_name

  tags = {
    Project     = "sorcerers-stone"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Block all public access (INV-1)
resource "aws_s3_bucket_public_access_block" "backups" {
  bucket                  = aws_s3_bucket.backups.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning — retain previous backups
resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption (belt — client-side age is the suspenders per INV-1)
resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Lifecycle: Standard → IA (30d) → Glacier (180d) → expire noncurrent (365d)
resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "backup-lifecycle"
    status = "Enabled"

    filter {
      prefix = "${var.backup_prefix}/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 180
      storage_class = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# Bucket policy: deny non-TLS (INV-1) + deny unencrypted PUTs
resource "aws_s3_bucket_policy" "backups" {
  bucket = aws_s3_bucket.backups.id
  # Wait for public access block before applying policy
  depends_on = [aws_s3_bucket_public_access_block.backups]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonTLS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.backups.arn,
          "${aws_s3_bucket.backups.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "DenyUnencryptedPuts"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.backups.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      },
      {
        Sid       = "AllowBackupAgentOnly"
        Effect    = "Allow"
        Principal = {
          AWS = aws_iam_user.backup_agent.arn
        }
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.backups.arn,
          "${aws_s3_bucket.backups.arn}/${var.backup_prefix}/*"
        ]
      }
    ]
  })
}

# ── IAM User (scoped to one prefix, no delete) ────────────────────────────────

resource "aws_iam_user" "backup_agent" {
  name = var.iam_username
  path = "/sorcerers-stone/"

  tags = {
    Project   = "sorcerers-stone"
    ManagedBy = "terraform"
  }
}

resource "aws_iam_user_policy" "backup_agent" {
  name = "ss-backup-agent-policy"
  user = aws_iam_user.backup_agent.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BackupPrefixReadWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
        ]
        Resource = "${aws_s3_bucket.backups.arn}/${var.backup_prefix}/*"
      },
      {
        Sid      = "ListBucket"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.backups.arn
        Condition = {
          StringLike = {
            "s3:prefix" = ["${var.backup_prefix}/*"]
          }
        }
      }
      # Intentionally NO s3:DeleteObject — backups are lifecycle-managed only
    ]
  })
}

# Access key for the backup agent (stored as UNRAID Docker secret)
resource "aws_iam_access_key" "backup_agent" {
  user = aws_iam_user.backup_agent.name
}

# ── Outputs (record in PROJECT_SPEC.md §10) ───────────────────────────────────

output "bucket_arn" {
  description = "S3 bucket ARN — record in PROJECT_SPEC.md §10"
  value       = aws_s3_bucket.backups.arn
}

output "bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.backups.id
}

output "iam_user_arn" {
  description = "IAM backup agent user ARN — record in PROJECT_SPEC.md §10"
  value       = aws_iam_user.backup_agent.arn
}

output "access_key_id" {
  description = "IAM access key ID — store as UNRAID Docker secret aws_access_key_id"
  value       = aws_iam_access_key.backup_agent.id
}

output "secret_access_key" {
  description = "IAM secret key — store as UNRAID Docker secret aws_secret_access_key (sensitive)"
  value       = aws_iam_access_key.backup_agent.secret
  sensitive   = true
}

output "backup_prefix" {
  description = "S3 key prefix for backup objects"
  value       = "${aws_s3_bucket.backups.id}/${var.backup_prefix}/"
}
