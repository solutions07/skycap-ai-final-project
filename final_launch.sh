#!/usr/bin/env bash
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${YELLOW}[SkyCap][Launch]${NC} $*"; }
ok() { echo -e "${GREEN}[SkyCap][OK]${NC} $*"; }
err() { echo -e "${RED}[SkyCap][Error]${NC} $*"; }

# 1) Activate venv
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -d .venv ]]; then
    log "Activating virtual environment (.venv)"
    # shellcheck disable=SC1091
    source .venv/bin/activate
  else
    err "No .venv found. Please create it first: python3 -m venv .venv"
    exit 1
  fi
fi
ok "Virtual environment active: ${VIRTUAL_ENV}"

# 2) Install dependencies
log "Installing dependencies from requirements.txt"
pip install -r requirements.txt
ok "Dependencies installed"

# 3) Build semantic index
if [[ -f build_index.py ]]; then
  log "Building semantic index (semantic_index.pkl)"
  if python3 build_index.py --out semantic_index.pkl; then
    ok "Semantic index built"
  else
    err "Index build failed; continuing without semantic search (fallbacks still available)"
  fi
else
  log "build_index.py not found; skipping index build"
fi

# 4) Run full test suite
log "Running unit tests"
python3 -m unittest -q || { err "Tests failed"; exit 1; }
ok "All tests passed"

# 5) Git: stage, commit and merge feature into main
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
FEATURE_BRANCH="feature/activate-hybrid-brains"
log "Current branch: ${CURRENT_BRANCH}"

if [[ "${CURRENT_BRANCH}" != "${FEATURE_BRANCH}" ]]; then
  log "Checking out ${FEATURE_BRANCH}"
  git checkout "${FEATURE_BRANCH}" || true
fi

log "Staging changes"
git add -A

if ! git diff --cached --quiet; then
  git commit -m "chore(launch): finalize Hybrid Brain and deployment configs"
else
  log "No changes to commit"
fi

log "Pushing feature branch"
git push -u origin "${FEATURE_BRANCH}" || true

log "Merging feature branch into main"
# Ensure main is up to date and exists locally
if git show-ref --verify --quiet refs/heads/main; then
  git checkout main
else
  git checkout -b main origin/main || git checkout main
fi

git pull --ff-only origin main || true

git merge --no-edit --ff-only "${FEATURE_BRANCH}" || {
  err "Fast-forward merge failed. Please resolve manually."
  exit 1
}

# 6) Push main
log "Pushing main"
git push origin main
ok "Main branch updated"

# 7) Deploy via Cloud Build
if [[ -f cloudbuild.yaml ]]; then
  : "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT env var}"
  : "${GOOGLE_CLOUD_REGION:?Set GOOGLE_CLOUD_REGION env var}"
  SERVICE_NAME=${SERVICE_NAME:-skycap-ai-service}
  VERTEX_MODEL_NAME=${VERTEX_MODEL_NAME:-gemini-1.0-pro}
  SEMANTIC_INDEX_GCS_URI_SUB=${SEMANTIC_INDEX_GCS_URI:-}
  log "Deploying to Cloud Run via Cloud Build (service=${SERVICE_NAME}, region=${GOOGLE_CLOUD_REGION})"
  gcloud builds submit --config cloudbuild.yaml --substitutions=_SERVICE_NAME=${SERVICE_NAME},_REGION=${GOOGLE_CLOUD_REGION},_VERTEX_MODEL_NAME=${VERTEX_MODEL_NAME},_SEMANTIC_INDEX_GCS_URI=${SEMANTIC_INDEX_GCS_URI_SUB}
  ok "Deployment triggered"
else
  err "cloudbuild.yaml not found; cannot deploy"
  exit 1
fi

ok "Final launch sequence completed"
