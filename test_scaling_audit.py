import pytest
from extract_financials import format_currency

def test_format_currency_billions():
    assert format_currency(1_081_000_000).startswith('₦1.081') and 'billion' in format_currency(1_081_000_000)

def test_format_currency_millions():
    assert format_currency(25_500_000).startswith('₦25.500') and 'million' in format_currency(25_500_000)

def test_format_currency_thousands():
    assert format_currency(250_000).startswith('₦250.000') and 'thousand' in format_currency(250_000)

def test_format_currency_small():
    assert format_currency(950) == '₦950.00'
