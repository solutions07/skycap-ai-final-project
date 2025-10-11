# Changelog

All notable changes to this project will be documented in this file.

## [1.0.5] - 2025-10-11

- Deploy revision: `skycap-live-service-00023-zzj`
- Image: `gcr.io/skycap-ai-final-project/skycap-live-service:fix-meta-2`
- Backend URL: https://skycap-live-service-472059152731.europe-west1.run.app
- Frontend URL: https://solutions07.github.io/skycap-ai-final-project/

Enhancements:
- GeneralKnowledgeEngine: explicit key contact/introducer response for AMD → Skyview (Emmanuel Oladimeji).
- LocationDataEngine: hardened phone detection using word boundaries to prevent false positives (e.g., 'tel' in 'tell').
- CompanyProfileEngine: valuation tools handler returning the exact KB statement when asked.

Validation:
- Test 5 (Key Contact): returns correct introducer line for Mr. Emmanuel Oladimeji.
- Test 6 (Testimonial): returns the exact quoted testimonial for Emmanuel Oladimeji.
- Test 7 (Valuation Tools): returns the exact KB line about tools used for valuation.

## [1.0.4] - 2025-10-11

- Deploy revision: `skycap-live-service-00021-8rf`
- Image: `gcr.io/skycap-ai-final-project/skycap-live-service:feat-oladimeji-1`
- Backend URL: https://skycap-live-service-472059152731.europe-west1.run.app
- Frontend URL: https://solutions07.github.io/skycap-ai-final-project/

Enhancements:
- GeneralKnowledgeEngine: precise testimonial handling for Emmanuel Oladimeji, returns the exact quoted line from KB.
- Financial comparative/trend logic hardening already live; preserved.
- Unified CORS policy verified for origin https://solutions07.github.io.

Validation:
- OPTIONS /ask preflight: 204 with ACAO header set to GitHub Pages origin.
- POST /ask with query "Share a testimonial from Emmanuel Oladimeji" returns the exact quote.

## [1.0.3] - 2025-10-11
- Comparative/trend year parsing fixes; year-end preference respected.
- Redeployed with successful validation.

## [1.0.2] - 2025-10-11
- Fix SyntaxError in intelligent_agent.py causing 503s.
- Health restored; CORS verified.

## [1.0.1] - 2025-10-10
- Unified CORS configuration in app.py; frontend wired to Cloud Run.

## [1.0.0] - 2025-10-10
- Initial hardened release with full Validation Gauntlet pass.# Changelog

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
