# Changelog

All notable changes for the final SkyCap AI deployment.

## v1.3.0 – 2025-10-07

Enhancements
- Hybrid routing: Prioritize Vertex AI for complex/general queries (policy/principles/explain/draft/capitals/minister) to avoid Brain 1 misroutes.
- Vertex fallback: Default to europe-west1 with `gemini-2.5-flash`; robust retry and result parsing.
- Semantic stability: `numpy<2` to ensure Torch CPU compatibility; lazy embedding with /tmp persistence.

Fixes
- Financial: Correct P/E computation (price ÷ EPS) using JAIZBANK market data aligned to report dates.
- Financial: Added guardrails (MIN_EPS_FOR_PE=0.05, MAX_PE_ALLOWED=150) to filter unrealistic ratios.
- Profile engine: Tightened "services" detection to prevent accidental matches in security policy questions.
- CORS: Global preflight handling, after_request headers, and OPTIONS catch-all for GitHub Pages frontend.
- YAML: Normalized `cloudbuild.yaml` to block lists and Artifact Registry paths.

UI
- Removed default suggestion shortcuts below the input box per client request.

DevOps / Deployment
- Cloud Build machine type set to `E2_HIGHCPU_8`.
- Moved images to Artifact Registry and set Cloud Run runtime service account.
- Added `/status` endpoint and service config archival.

Verification
- Complex policy query returns `provenance: VertexAI`.
- Highest P/E query returns a realistic capped value (e.g., 92.00) with detailed breakdown.
