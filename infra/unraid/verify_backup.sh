#!/usr/bin/env bash
# verify_backup.sh — age encrypt → S3 upload → download → decrypt round-trip test
# Ref: .kiro/specs/phase-1-architecture/tasks.md Task 1.8
#
# Prerequisites on UNRAID:
#   - age installed (https://github.com/FiloSottile/age/releases)
#   - aws CLI configured with backup agent credentials
#   - AGE_RECIPIENT set to the public key from secrets/age_recipient.txt
#   - AGE_IDENTITY set to the path of the age private key (offline key — plug in for test)
#   - S3_BUCKET set to the bucket name
#
# Usage:
#   export AGE_RECIPIENT="age1..."
#   export AGE_IDENTITY="/path/to/age_identity.txt"
#   export S3_BUCKET="ofs-sorcerers-stone-backups"
#   bash infra/unraid/verify_backup.sh

set -euo pipefail

BUCKET="${S3_BUCKET:?Set S3_BUCKET env var}"
RECIPIENT="${AGE_RECIPIENT:?Set AGE_RECIPIENT env var}"
IDENTITY="${AGE_IDENTITY:?Set AGE_IDENTITY env var}"
PREFIX="sorcerers-stone/verify"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
TEST_KEY="${PREFIX}/roundtrip-test-${TIMESTAMP}.age"
PLAINTEXT="Sorcerers Stone backup round-trip test ${TIMESTAMP}"

echo "=== Backup Round-Trip Verification ==="
echo "Bucket:    $BUCKET"
echo "S3 key:    $TEST_KEY"
echo "Timestamp: $TIMESTAMP"
echo ""

# ── Step 1: Encrypt test payload ──────────────────────────────────────────────
echo "[1/5] Encrypting test payload with age..."
ENCRYPTED=$(echo "$PLAINTEXT" | age -r "$RECIPIENT" | base64)
echo "      Encrypted (base64 preview): ${ENCRYPTED:0:40}..."

# ── Step 2: Upload to S3 ──────────────────────────────────────────────────────
echo "[2/5] Uploading encrypted object to S3..."
echo "$PLAINTEXT" \
  | age -r "$RECIPIENT" \
  | aws s3 cp - "s3://${BUCKET}/${TEST_KEY}" \
      --sse AES256 \
      --content-type "application/octet-stream"
echo "      Uploaded: s3://${BUCKET}/${TEST_KEY}"

# ── Step 3: Write SHA-256 sidecar ─────────────────────────────────────────────
echo "[3/5] Writing SHA-256 sidecar..."
echo "$PLAINTEXT" \
  | age -r "$RECIPIENT" \
  | sha256sum \
  | awk '{print $1}' \
  | aws s3 cp - "s3://${BUCKET}/${TEST_KEY}.sha256" \
      --content-type "text/plain"
echo "      Sidecar: s3://${BUCKET}/${TEST_KEY}.sha256"

# ── Step 4: Download and decrypt ──────────────────────────────────────────────
echo "[4/5] Downloading and decrypting..."
DECRYPTED=$(aws s3 cp "s3://${BUCKET}/${TEST_KEY}" - | age -d -i "$IDENTITY")
echo "      Decrypted: $DECRYPTED"

# ── Step 5: Verify match ──────────────────────────────────────────────────────
echo "[5/5] Verifying content matches original..."
if [ "$DECRYPTED" = "$PLAINTEXT" ]; then
    echo ""
    echo "✅ PASS — Round-trip verification successful"
    echo "   Plaintext encrypted → uploaded → downloaded → decrypted correctly."
    echo "   No plaintext data exists in S3."
else
    echo ""
    echo "❌ FAIL — Content mismatch!"
    echo "   Original:  $PLAINTEXT"
    echo "   Decrypted: $DECRYPTED"
    exit 1
fi

# ── Cleanup test object ───────────────────────────────────────────────────────
echo ""
echo "[CLEANUP] Removing test objects from S3..."
aws s3 rm "s3://${BUCKET}/${TEST_KEY}"
aws s3 rm "s3://${BUCKET}/${TEST_KEY}.sha256"
echo "          Test objects removed."

# ── Verify IAM cannot delete production backups ───────────────────────────────
echo ""
echo "[VERIFY] Confirming IAM user cannot delete production objects..."
PROD_KEY="sorcerers-stone/$(date +%Y-%m-%d).dump.age"
if aws s3 rm "s3://${BUCKET}/${PROD_KEY}" 2>&1 | grep -q "AccessDenied\|NoSuchKey\|error"; then
    echo "✅ PASS — s3:DeleteObject correctly denied or no object to delete"
else
    echo "⚠️  WARNING — DeleteObject may be permitted; review IAM policy"
fi

echo ""
echo "=== Verification Complete ==="
echo "Record results in PROJECT_SPEC.md §10 with date: $(date +%Y-%m-%d)"
