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
