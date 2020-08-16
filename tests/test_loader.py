"""Test the loader"""

from aiofix.loader.loader import load_protocol


def test_loader():
    """Test the loader"""
    assert load_protocol('etc/FIX40.yaml') is not None
    assert load_protocol('etc/FIX41.yaml') is not None
    assert load_protocol('etc/FIX42.yaml') is not None
    assert load_protocol('etc/FIX43.yaml') is not None
    assert load_protocol('etc/FIX44.yaml') is not None
