#!/usr/bin/env bash
# Sync the CV everywhere it lives. Run after editing cv.tex and/or cv.md.
#
#   cv.tex ──pdflatex──▶ cv.pdf ──▶ s3://ed7-cv-agent-assets/cv.pdf
#                                    (served by the agent's get_cv_download_link
#                                     tool as a 15-minute presigned URL)
#   cv.md  ─────────────────────▶ Secrets Manager: cv-agent/cv
#                                    (the agent's knowledge — picked up at the
#                                     next runtime cold start, no redeploy)
#
# Both sources live outside the repo on purpose (personal data):
#   CV_TEX_DIR  defaults to ~/Desktop/CV/latex
#   CV_MD       defaults to app/src/cv_agent/data/cv.md (gitignored)

set -euo pipefail

CV_TEX_DIR="${CV_TEX_DIR:-$HOME/Desktop/CV/latex}"
CV_MD="${CV_MD:-$(cd "$(dirname "$0")/.." && pwd)/app/src/cv_agent/data/cv.md}"
BUCKET="ed7-cv-agent-assets"
SECRET_ID="cv-agent/cv"
REGION="eu-west-1"

echo "▸ Compiling cv.tex → cv.pdf"
(cd "$CV_TEX_DIR" && pdflatex -interaction=nonstopmode cv.tex > /dev/null \
                  && pdflatex -interaction=nonstopmode cv.tex > /dev/null)
echo "  $(pdfinfo "$CV_TEX_DIR/cv.pdf" 2>/dev/null | grep Pages || true)"

echo "▸ Uploading cv.pdf → s3://$BUCKET/cv.pdf"
aws s3 cp "$CV_TEX_DIR/cv.pdf" "s3://$BUCKET/cv.pdf" --region "$REGION" \
  --content-type application/pdf --only-show-errors
echo "  done"

if [ -f "$CV_MD" ]; then
  echo "▸ Updating Secrets Manager: $SECRET_ID (agent knowledge)"
  aws secretsmanager put-secret-value --secret-id "$SECRET_ID" \
    --secret-string "file://$CV_MD" --region "$REGION" \
    --query VersionId --output text
else
  echo "▸ Skipping secret update ($CV_MD not found)"
fi

echo "✓ CV synced everywhere."
