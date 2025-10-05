# SkyCap AI – V1.1 Release Notes

This project is a Python Flask application with an on-premise intelligent agent backend. The V1.1 update delivers a critical backend hardening and two user-facing enhancements.

## New in V1.1

### 1) Backend Stability: Comparison Logic Hardening
- The financial comparison workflow (e.g., "Compare Total Assets between 2022 and 2023") has been audited and hardened to handle malformed input, missing years, and zero baselines without crashing.
- The engine now safely returns a professional message when there is insufficient data for a requested comparison, and it provides clear wording when the initial (old) value is zero.

### 2) Dark Mode (Frontend)
- A Dark Mode toggle has been added to the header.
- Implementation uses CSS variables (`:root` and `:root[data-theme="dark"]`) to ensure a cohesive, professional dark theme across the app.
- The user’s theme preference is persisted with `localStorage` under the key `skycap_theme`. On first load, the UI respects the system preference (`prefers-color-scheme`).

### 3) Expanded Suggestions (Frontend)
- The dropdown "Suggested questions" list has been expanded to include identity/meta, personnel, company profile, contact/location, financial metrics, comparative analysis, and market data queries.

## New Automated Test

### `test_comparison_engine.py`
- Purpose: Validates the hardened comparative analysis behavior in the financial engine.
- Coverage:
  - Valid comparison between two years returns a proper "Comparing…" response and includes both years.
  - Missing requested year leads to a safe, non-crashing "Insufficient data" message.
  - Zero-baseline scenario (old value is 0) returns a clear, specific message indicating the transition from ₦0 to the new value.

Run the test suite:

```bash
python3 -m unittest -q
```

All tests should pass along with the existing hardening and routing tests.

## Notes
- Backend: `intelligent_agent.py` contains the hardened comparison logic in the `FinancialDataEngine` and resilience improvements in `_find_best_date_match`.
- Frontend: `index.html` includes the Dark Mode toggle and the expanded suggestions list.
- No new runtime dependencies were added in this release.

## New in V1.2

### 1) Currency Scaling Correction
- Financial metrics sourced from reports are expressed in thousands. The formatter now multiplies by 1,000 before rendering values with NGN units and appropriate magnitude (Million/Billion/Trillion).
- Example: `580131058.0` is displayed as `₦580.131 Billion`.

### 2) Profile Q&A Enhancements
- Company profile engine answers:
  - Client types/clientele (e.g., government parastatals, multinational/indigenous companies, HNIs).
  - Research report types (e.g., Skyview Research Report, Weekly, Monthly, Quarterly, Annual Reports).

### 3) New Automated Tests
- `test_profile_queries.py` validates the new profile answers for client types and research report types.
- Full suite (including comparison tests) remains green.

## How scaling works (examples)

Source financial metrics in the knowledge base are expressed in thousands. The formatter converts them to full NGN amounts and applies a readable unit (Million/Billion/Trillion). Earnings per share (EPS) is not scaled and shows as a plain number.

- Input (thousands): 580131058.0 — Metric: Total Assets → Output: ₦580.131 Billion
- Input (thousands): 11053595.0 — Metric: Profit Before Tax → Output: ₦11.054 Billion
- Input (thousands): 16508278.0 — Metric: Gross Earnings → Output: ₦16.508 Billion
- Input (plain): 2.77 — Metric: Earnings per share (EPS) → Output: 2.77 (no currency, no scaling)

Implementation note: Scaling and formatting are handled in `intelligent_agent.py` by `_format_large_number` (thousands → NGN with units) and `_format_metric_value` (routes currency metrics vs EPS).

## AMD AI Synergy Hub: Standard Operating Procedure (SOP) V1.0

This document outlines the mandatory, professional workflow for all AI agent development. It is designed to ensure stability, prevent errors, and maintain a high standard of quality.

Core Principles
Work in an Isolated Environment: All development must occur on the designated development VM and within a project-specific Python virtual environment (.venv).

Never Work on main Directly: The main branch is the stable Master Blueprint. It is for production-ready code only.

Create a "Photocopy" Branch for All New Work: All new features and bug fixes must be developed on a separate, temporary branch.

Test Before You Merge: All new code must be accompanied by automated tests, and the full test suite must pass before merging.

The 5-Phase Development Protocol
Phase 1: Mission Briefing & Setup

Start and connect to the development VM.

Navigate to the project folder and activate the virtual environment: source .venv/bin/activate.

Ensure you have the latest code: git checkout main followed by git pull origin main.

Phase 2: Create a Safe Workspace

Create a new branch for your task: git checkout -b [your-feature-name].

Phase 3: Development & Local Validation

Perform the mandated coding tasks.

Create or update automated tests for the new code.

Run the full test suite to ensure no regressions: python3 -m unittest -q.

Phase 4: Code Review & Merge

Save the work to the feature branch: git add ., git commit -m "Your message.", git push -u origin [your-feature-name].

Merge the perfected code into the Master Blueprint: git checkout main followed by git merge [your-feature-name].

Phase 5: Final Launch (Deployment)

Push the updated main branch to the official repository: git push origin main.

Deploy the final backend service: gcloud run deploy ....
