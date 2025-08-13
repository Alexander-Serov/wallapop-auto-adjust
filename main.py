#!/usr/bin/env python3

import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
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
    
    # Get credentials from .env or prompt
    print("\n1. Logging into Wallapop...")
    email = os.getenv('WALLAPOP_EMAIL') or input("Email: ")
    password = os.getenv('WALLAPOP_PASSWORD') or input("Password: ")
    
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
    main()