"""Test that all modules can be imported without errors."""

import pytest


def test_main_package_import():
    """Test that the main package can be imported."""
    import wallapop_auto_adjust
    assert wallapop_auto_adjust is not None


def test_config_module_import():
    """Test that the config module can be imported."""
    from wallapop_auto_adjust import config
    assert config is not None


def test_session_manager_import():
    """Test that the session_manager module can be imported."""
    from wallapop_auto_adjust import session_manager
    assert session_manager is not None


def test_cli_module_import():
    """Test that the cli module can be imported."""
    from wallapop_auto_adjust import cli
    assert cli is not None


def test_wallapop_client_import():
    """Test that the wallapop_client module can be imported."""
    from wallapop_auto_adjust import wallapop_client
    assert wallapop_client is not None


def test_price_adjuster_import():
    """Test that the price_adjuster module can be imported."""
    from wallapop_auto_adjust import price_adjuster
    assert price_adjuster is not None


def test_api_analyzer_import():
    """Test that the api_analyzer module can be imported."""
    from wallapop_auto_adjust import api_analyzer
    assert api_analyzer is not None