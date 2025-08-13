#!/usr/bin/env python3

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config import ConfigManager
from wallapop_client import WallapopClient
from price_adjuster import PriceAdjuster

def main():
    print("Wallapop Auto Price Adjuster")
    print("=" * 30)
    
    # Initialize components
    config_manager = ConfigManager()
    wallapop_client = WallapopClient()
    price_adjuster = PriceAdjuster(wallapop_client, config_manager)
    
    # Login (uses session persistence)
    print("\n1. Authenticating...")
    email = os.getenv('WALLAPOP_EMAIL') or input("Email: ")
    password = os.getenv('WALLAPOP_PASSWORD') or input("Password: ")
    
    if not wallapop_client.login(email, password):
        print("✗ Authentication failed")
        return
    
    print("✓ Authentication successful")
    
    # Get and update product configuration
    print("\n2. Fetching products...")
    products = wallapop_client.get_user_products()
    
    if not products:
        print("✗ No products found")
        return
    
    print(f"✓ Found {len(products)} products")
    
    # Update configuration with discovered products
    config_manager.update_products(products)
    config_manager.save_config()
    print(f"✓ Configuration updated: {config_manager.config_path}")
    
    # Process price adjustments
    print(f"\n3. Processing adjustments (delay: {config_manager.get_delay_days()} days)...")
    updated_count = 0
    
    for product in products:
        if price_adjuster.adjust_product_price(product):
            updated_count += 1
    
    # Save final configuration
    config_manager.save_config()
    
    print(f"\n✓ Process completed. Updated {updated_count} products.")

if __name__ == "__main__":
    main()