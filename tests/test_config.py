"""Test basic functionality of the ConfigManager class."""

import json
import os
import tempfile
from datetime import datetime
import pytest

from wallapop_auto_adjust.config import ConfigManager


class TestConfigManager:
    """Test cases for ConfigManager class."""

    def test_config_manager_creation(self):
        """Test that ConfigManager can be instantiated."""
        # Use a non-existent path so default config is used
        config_path = "/tmp/non_existent_config_file.json"
            
        config_manager = ConfigManager(config_path)
        assert config_manager is not None
        assert config_manager.config_path == config_path

    def test_default_config_structure(self):
        """Test that the default config has the expected structure."""
        # Use a non-existent path so default config is used
        config_path = "/tmp/non_existent_config_file2.json"
            
        config_manager = ConfigManager(config_path)
        assert "products" in config_manager.config
        assert "settings" in config_manager.config
        assert isinstance(config_manager.config["products"], dict)
        assert isinstance(config_manager.config["settings"], dict)

    def test_save_and_load_config(self):
        """Test that config can be saved and loaded."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            config_path = tmp.name
            
        try:
            # Create and save config (start with non-existent file to get defaults)
            os.unlink(config_path)  # Remove the empty file
            config_manager = ConfigManager(config_path)
            config_manager.config["test_key"] = "test_value"
            config_manager.save_config()
            
            # Load config in new instance
            new_config_manager = ConfigManager(config_path)
            assert new_config_manager.config["test_key"] == "test_value"
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)

    def test_get_delay_days(self):
        """Test get_delay_days method."""
        # Use a non-existent path so default config is used
        config_path = "/tmp/non_existent_config_file3.json"
            
        config_manager = ConfigManager(config_path)
        # Default should be 1
        assert config_manager.get_delay_days() == 1
        
        # Set custom value
        config_manager.config["settings"]["delay_days"] = 5
        assert config_manager.get_delay_days() == 5