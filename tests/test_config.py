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
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
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

    def test_remove_sold_products(self):
        """Test remove_sold_products method."""
        config_path = "/tmp/non_existent_config_file4.json"
        config_manager = ConfigManager(config_path)

        # Set up initial config with some products
        config_manager.config["products"] = {
            "12345": {
                "title": "Product 1",
                "current_price": 100,
                "last_updated": "2024-01-01T10:00:00",
            },
            "67890": {
                "title": "Product 2",
                "current_price": 200,
                "last_updated": "2024-01-01T10:00:00",
            },
            "11111": {
                "title": "Product 3",
                "current_price": 300,
                "last_updated": "2024-01-01T10:00:00",
            },
        }

        # Mock current products from API (Product 2 is sold/missing)
        current_products = [
            {"id": "12345", "title": "Product 1", "price": 100},
            {"id": "11111", "title": "Product 3", "price": 300},
            {"id": "22222", "title": "Product 4", "price": 400},  # New product
        ]

        # Test removing sold products
        removed_products = config_manager.remove_sold_products(current_products)

        # Should return the removed product name
        assert removed_products == ["Product 2"]

        # Config should no longer contain the sold product
        assert "67890" not in config_manager.config["products"]
        assert "12345" in config_manager.config["products"]  # Still there
        assert "11111" in config_manager.config["products"]  # Still there

        # Test when no products are sold
        removed_products = config_manager.remove_sold_products(current_products)
        assert removed_products == []

        # Test with empty current products (all sold)
        all_removed = config_manager.remove_sold_products([])
        assert set(all_removed) == {"Product 1", "Product 3"}
        assert config_manager.config["products"] == {}
