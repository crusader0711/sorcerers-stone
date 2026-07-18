# AWS Foundation Runbook — Task 1.8
# Ref: .kiro/specs/phase-1-architecture/tasks.md Task 1.8

## Overview

This runbook provisions the AWS backup lane for The Sorcerer's Stone.
All resources are defined in `infra/terraform/main.tf`.

**Security posture (INV-1):**
- S3 bucket rejects all non-TLS connections
- Plaintext is never written to S3 — only age-encrypted objects
- IAM user has no `s3:DeleteObject` — lifecycle policies manage retention
- Client-side age encryption is the primary guard; SSE-AES256 is belt-and-suspenders

---

## Step 1 — Apply Terraform

```bash
cd infra/terraform

# Initialize (downloads AWS provider)
terraform init

# Preview what will be created
terraform plan -out=tfplan

# Apply (creates bucket, IAM user, policy)
terraform apply tfplan
```

**Expected output:**
```
bucket_arn         = "arn:aws:s3:::ofs-sorcerers-stone-backups"
bucket_name        = "ofs-sorcerers-stone-backups"
iam_user_arn       = "arn:aws:iam::ACCOUNT:user/sorcerers-stone/ss-backup-agent"
access_key_id      = "AKIA..."
backup_prefix      = "ofs-sorcerers-stone-backups/sorcerers-stone/"
```

The `secret_access_key` is marked sensitive — retrieve it with:
```bash
terraform output -raw secret_access_key
```

---

## Step 2 — Store Credentials on UNRAID

Once UNRAID is ready (3 weeks):

```bash
# Write IAM credentials to UNRAID secrets directory
echo "AKIA_YOUR_ACCESS_KEY_ID" \
  > /mnt/user/appdata/sorcerers-stone/secrets/aws_access_key_id.txt

terraform output -raw secret_access_key \
  > /mnt/user/appdata/sorcerers-stone/secrets/aws_secret_access_key.txt

chmod 600 /mnt/user/appdata/sorcerers-stone/secrets/aws_access_key_id.txt
chmod 600 /mnt/user/appdata/sorcerers-stone/secrets/aws_secret_access_key.txt
```

---

## Step 3 — Generate age Keypair

```bash
# Install age (if not present on UNRAID)
# Download from: https://github.com/FiloSottile/age/releases

# Generate keypair
age-keygen 2>&1 | tee /tmp/age_keygen_output.txt

# Extract and store PUBLIC key only on UNRAID
grep "public key" /tmp/age_keygen_output.txt | awk '{print $NF}' \
  > /mnt/user/appdata/sorcerers-stone/secrets/age_recipient.txt
chmod 600 /mnt/user/appdata/sorcerers-stone/secrets/age_recipient.txt

# PRIVATE key — copy to password manager + print for escrow
# Then SECURELY DELETE from UNRAID:
shred -u /tmp/age_keygen_output.txt
```

> **CRITICAL:** The age private key must NEVER reside on the UNRAID host permanently.
> It is only needed for restore operations. Store it offline.

---

## Step 4 — Run Round-Trip Verification

```bash
export AGE_RECIPIENT=$(cat /mnt/user/appdata/sorcerers-stone/secrets/age_recipient.txt)
export AGE_IDENTITY="/path/to/offline/age_identity.txt"   # plug in USB/offline key
export S3_BUCKET="ofs-sorcerers-stone-backups"

# Configure AWS CLI with backup agent credentials
aws configure --profile ss-backup
# Enter: access key ID, secret key, region, output format (json)

AWS_PROFILE=ss-backup bash infra/unraid/verify_backup.sh
```

**Expected output:**
```
✅ PASS — Round-trip verification successful
✅ PASS — s3:DeleteObject correctly denied
```

---

## Step 5 — Record ARNs in PROJECT_SPEC.md

After apply, update `PROJECT_SPEC.md §10` (Runbooks Index):

```markdown
## 10. Runbooks Index

### AWS Resources (provisioned YYYY-MM-DD)
- S3 Bucket ARN:       arn:aws:s3:::ofs-sorcerers-stone-backups
- IAM User ARN:        arn:aws:iam::ACCOUNT_ID:user/sorcerers-stone/ss-backup-agent
- Backup prefix:       sorcerers-stone/
- Round-trip verified: YYYY-MM-DD ✅
```

---

## Acceptance Criteria Checklist

- [ ] `terraform apply` completes with no errors
- [ ] S3 bucket rejects HTTP PUT: `curl http://ofs-sorcerers-stone-backups.s3.amazonaws.com/ -v` → 403
- [ ] IAM user `s3:DeleteObject` returns AccessDenied
- [ ] age round-trip test passes (`verify_backup.sh` exits 0)
- [ ] No plaintext object in bucket after test (only `.age` files)
- [ ] ARNs recorded in `PROJECT_SPEC.md §10`
- [ ] age private key moved offline ✅
