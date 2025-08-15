#!/usr/bin/env python3

"""
Wallapop Auto Price Adjuster CLI (packaged)
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

from wallapop_auto_adjust.config import ConfigManager
from wallapop_auto_adjust.wallapop_client import WallapopClient
from wallapop_auto_adjust.price_adjuster import PriceAdjuster


def main() -> None:
    print("Wallapop Auto Price Adjuster")
    print("=" * 30)

    # Initialize components
    config_manager = ConfigManager()
    wallapop_client = WallapopClient()
    price_adjuster = PriceAdjuster(wallapop_client, config_manager)

    # Get credentials from .env or prompt
    print("\n1. Logging into Wallapop...")
    email = os.getenv("WALLAPOP_EMAIL") or input("Email: ")
    password = os.getenv("WALLAPOP_PASSWORD") or input("Password: ")

    if not wallapop_client.login(email, password):
        print("Login failed. Please check credentials and try again.")
        return

    # Get user products
    print("\n2. Fetching your products...")
    products = wallapop_client.get_user_products()

    if not products:
        print("No products found or API not implemented yet.")
        return

    # Update config with discovered products
    print(f"\n3. Found {len(products)} products. Updating configuration...")
    config_manager.update_products(products)
    config_manager.save_config()

    # Process price adjustments
    print("\n4. Processing price adjustments...")
    updated_count = 0

    for product in products:
        if price_adjuster.adjust_product_price(product):
            updated_count += 1

    # Save final config
    config_manager.save_config()

    print(f"\n✓ Process completed. Updated {updated_count} products.")
    print(f"Configuration saved to: {config_manager.config_path}")


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10+ is required. Please upgrade your Python interpreter.")
    main()
