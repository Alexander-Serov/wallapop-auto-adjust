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
from wallapop_auto_adjust.session_persistence import SessionPersistenceManager
import importlib


def main() -> None:
    print("Wallapop Auto Price Adjuster")
    print("=" * 30)

    # Initialize components
    config_manager = ConfigManager()
    spm = SessionPersistenceManager()
    print("\n1. Logging into Wallapop (session-first)...")

    # 1) Try session-based auth first (from ~/.wallapop-auto-adjust)
    session_ok = spm.load_session()
    if session_ok:
        ok, token_or_err = spm.refresh_access_token()
        session_ok = ok
        if not ok:
            print(f"   ⚠️ Session refresh failed: {token_or_err}")
    else:
        print("   ℹ️ No existing session found.")

    # 2) If no session, offer Automatic (selenium) or Manual cookie copy
    if not session_ok:
        print("\nNo valid session. Choose a login method:")
        print("  1) Automatic login (browser automation)")
        print("  2) Manual cookie copy (guided)")
        choice = (
            os.getenv("WALLAPOP_LOGIN_METHOD") or input("Select [1/2] (default 2): ")
        ).strip() or "2"

        if choice == "1":
            # Automatic login via modern client
            try:
                # Use WallapopClient's built-in automatic login
                auto_client = WallapopClient()
                email = os.getenv("WALLAPOP_EMAIL") or input("Email: ")
                password = os.getenv("WALLAPOP_PASSWORD") or input("Password: ")
                if not auto_client.login(email, password):
                    print("Login failed. Please try manual cookie copy.")
                    return
                # Proceed with a valid session
            except Exception as e:
                print(f"Automatic login failed to start: {e}")
                print("Please choose manual cookie copy next time.")
                return
        else:
            # Manual cookie copy via packaged guide
            try:
                from wallapop_auto_adjust.cookie_extraction_guide import (
                    CookieExtractionGuide,
                )

                guide = CookieExtractionGuide()
                if not guide.run():
                    print("Manual cookie extraction did not complete. Exiting.")
                    return
            except Exception as e:
                print(f"Manual cookie extraction error: {e}")
                return

    # With a valid/renewable session, use the modern client (it will load the session)
    wallapop_client = WallapopClient()
    price_adjuster = PriceAdjuster(wallapop_client, config_manager)

    # Get user products
    print("\n2. Fetching your products...")
    products = wallapop_client.get_user_products()

    if not products:
        print("No products found. This could be due to:")
        print("  - No products listed on your account")
        print("  - Expired session (try re-running the application)")
        print("  - API authentication issues")
        return

    # Update config with discovered products
    print(f"\n3. Found {len(products)} products. Updating configuration...")
    config_manager.update_products(products)

    # Remove sold products from config
    sold_products = config_manager.remove_sold_products(products)
    if sold_products:
        print(f"\n📦 Removed {len(sold_products)} sold product(s) from configuration:")
        for product_name in sold_products:
            print(f"   - {product_name}")
    else:
        print("\n✅ No sold products to remove from configuration.")

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
