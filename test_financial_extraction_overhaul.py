import json
import os
import pytest
from pathlib import Path

from extract_financials import run_extraction, KB_PATH, PRIMARY_METRICS

@pytest.fixture(scope='module')
def rebuilt_kb(tmp_path_factory):
    # Run extraction (non-destructive if PDFs absent)
    kb = run_extraction(save=False)
    return kb


def test_financial_reports_structure(rebuilt_kb):
    reports = rebuilt_kb.get('financial_reports', [])
    assert isinstance(reports, list)


def test_metrics_reason_presence(rebuilt_kb):
    for rpt in rebuilt_kb.get('financial_reports', [])[:10]:
        meta = rpt.get('report_metadata', {})
        if not isinstance(meta, dict):
            continue
        reasons = meta.get('_extraction_reasons', {})
        assert isinstance(reasons, dict)
        # Ensure each primary metric is either present or has a reason
        metrics = meta.get('metrics', {})
        for m in PRIMARY_METRICS:
            if m not in metrics:
                assert m in reasons


def test_eps_sanity(rebuilt_kb):
    # EPS values should be within plausible bounds
    for rpt in rebuilt_kb.get('financial_reports', [])[:25]:
        metrics = rpt.get('report_metadata', {}).get('metrics', {})
        if 'earnings per share' in metrics:
            val = metrics['earnings per share']
            assert 0 < float(val) < 100, f"Implausible EPS value: {val}"


def test_total_assets_reasonable(rebuilt_kb):
    for rpt in rebuilt_kb.get('financial_reports', [])[:25]:
        metrics = rpt.get('report_metadata', {}).get('metrics', {})
        if 'total assets' in metrics:
            assert float(metrics['total assets']) >= 1_000_000
