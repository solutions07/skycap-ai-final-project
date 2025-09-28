#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# SkyCap AI - Unified Backend Deployment Script (Cloud Shell)
#
# This script performs a full backend deployment of the SkyCap AI service
# to Google Cloud Run from a clean Cloud Shell environment.
#
# Actions:
#  1. Validate environment & tools
#  2. Set project & enable required APIs
#  3. Clone repository (fresh)
#  4. Build container image
#  5. Push image to Artifact Registry (preferred) or GCR fallback
#  6. Deploy to Cloud Run using the specified service account
#  7. Output the public service URL
#
# REQUIREMENTS (Cloud Shell already provides these):
#  - gcloud CLI authenticated (Cloud Shell auto-authenticated)
#  - Docker / Buildpacks via Cloud Build
#
# USAGE:
#   bash final_deploy.sh
#
###############################################################################

# ---- CONFIGURATION ----
PROJECT_ID="skycap-ai-final-project"
REGION="us-central1"
SERVICE_NAME="skycap-ai-service"
SERVICE_ACCOUNT="skycap-ai-server@skycap-ai-final-project.iam.gserviceaccount.com"
REPO_URL="https://github.com/solutions07/skycap-ai-final-project.git"
SOURCE_DIR="skycap-ai-final-project"
IMAGE_REPO="skycap-ai"              # repository name inside Artifact Registry
IMAGE_TAG="latest"
ARTIFACT_REPO_LOCATION="$REGION"
FULL_IMAGE_AR="${REGION}-docker.pkg.dev/${PROJECT_ID}/${IMAGE_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"
FALLBACK_GCR_IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:${IMAGE_TAG}"

# ---- FUNCTIONS ----
log() { printf "\n[INFO] %s\n" "$*"; }
warn() { printf "\n[WARN] %s\n" "$*"; }
err() { printf "\n[ERROR] %s\n" "$*" >&2; }

require_tool() {
  command -v "$1" >/dev/null 2>&1 || { err "Required tool '$1' not found in PATH"; exit 1; }
}

# ---- PRE-FLIGHT ----
log "Validating tools..."
require_tool gcloud
require_tool git

log "Setting active project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null

log "Enabling required APIs (idempotent)..."
APIS=( run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com )
for api in "${APIS[@]}"; do
  gcloud services enable "$api" --quiet || warn "API enable call for $api returned non-zero (may already be enabled)"
done

# ---- REPO CLONE ----
if [ -d "$SOURCE_DIR" ]; then
  warn "Existing directory $SOURCE_DIR detected. Removing for clean build context." 
  rm -rf "$SOURCE_DIR"
fi
log "Cloning repository..."
git clone --depth 1 "$REPO_URL" "$SOURCE_DIR"
cd "$SOURCE_DIR"

# ---- ARTIFACT REGISTRY SETUP ----
log "Ensuring Artifact Registry repository exists: ${IMAGE_REPO}"
if ! gcloud artifacts repositories describe "$IMAGE_REPO" --location="$ARTIFACT_REPO_LOCATION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$IMAGE_REPO" \
    --repository-format=docker \
    --location="$ARTIFACT_REPO_LOCATION" \
    --description="SkyCap AI container images" || { err "Failed to create Artifact Registry repository"; exit 1; }
fi

log "Configuring Docker auth for Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ---- BUILD & PUSH ----
if [ -f Dockerfile.production ]; then
  DOCKERFILE="Dockerfile.production"
elif [ -f Dockerfile ]; then
  DOCKERFILE="Dockerfile"
else
  err "No Dockerfile found. Aborting."; exit 1
fi

log "Building image with docker file: $DOCKERFILE"
# Prefer Cloud Build for reproducibility
if gcloud builds submit --tag "$FULL_IMAGE_AR" --gcs-log-dir="gs://$PROJECT_ID-cloudbuild-logs" --timeout=30m .; then
  FINAL_IMAGE="$FULL_IMAGE_AR"
else
  warn "Cloud Build failed or unavailable; attempting local Docker build & push (fallback)"
  require_tool docker
  docker build -f "$DOCKERFILE" -t "$FULL_IMAGE_AR" .
  docker push "$FULL_IMAGE_AR" || { warn "Artifact Registry push failed; trying GCR fallback"; \
    docker tag "$FULL_IMAGE_AR" "$FALLBACK_GCR_IMAGE"; docker push "$FALLBACK_GCR_IMAGE"; FINAL_IMAGE="$FALLBACK_GCR_IMAGE"; }
  [ -z "${FINAL_IMAGE:-}" ] && FINAL_IMAGE="$FULL_IMAGE_AR"
fi

# If FINAL_IMAGE not set by fallback path
FINAL_IMAGE="${FINAL_IMAGE:-$FULL_IMAGE_AR}"
log "Using image: $FINAL_IMAGE"

# ---- DEPLOY ----
log "Deploying to Cloud Run service: $SERVICE_NAME (region: $REGION)"
set +e
DEPLOY_OUTPUT=$(gcloud run deploy "$SERVICE_NAME" \
  --image "$FINAL_IMAGE" \
  --platform managed \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --allow-unauthenticated \
  --port 8080 \
  --quiet 2>&1)
DEPLOY_STATUS=$?
set -e

if [ $DEPLOY_STATUS -ne 0 ]; then
  err "Cloud Run deployment failed:\n$DEPLOY_OUTPUT"
  exit 1
fi

log "Parsing service URL..."
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)')
if [ -z "$SERVICE_URL" ]; then
  err "Failed to retrieve service URL."; exit 1
fi

log "Deployment successful!"
printf "\nService URL: %s\n" "$SERVICE_URL"

# ---- POST DEPLOY SUMMARY ----
cat <<EOF
==============================================================================
SkyCap AI Deployment Complete
------------------------------------------------------------------------------
Project:        $PROJECT_ID
Region:         $REGION
Service:        $SERVICE_NAME
Image:          $FINAL_IMAGE
Service Account:$SERVICE_ACCOUNT
Public URL:     $SERVICE_URL
==============================================================================
Next Steps:
 - Verify health endpoint:  curl -f $SERVICE_URL/health
 - Tail logs:              gcloud logs tail --project $PROJECT_ID --region $REGION --service $SERVICE_NAME
 - (Optional) Set traffic splits or revisions as needed.
==============================================================================
EOF
