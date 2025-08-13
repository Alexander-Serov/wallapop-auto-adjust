#!/usr/bin/env python3

import sys
import os
import json

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config import ConfigManager

def configure_products():
    config_manager = ConfigManager()
    
    if not config_manager.config.get("products"):
        print("No products found. Run the main script first to discover products.")
        return
    
    # Load current products with prices
    sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
    from wallapop_client import WallapopClient
    
    client = WallapopClient()
    if client.session_manager.load_session():
        current_products = {p['id']: p for p in client.get_user_products()}
    else:
        current_products = {}
    
    print("Product Configuration")
    print("=" * 30)
    print("Available adjustments:")
    print("  'keep' - No price change")
    print("  0.9    - Reduce price by 10%")
    print("  1.1    - Increase price by 10%")
    print("  etc.")
    print()
    
    products = config_manager.config["products"]
    
    for product_id, product_data in products.items():
        current_adjustment = product_data.get("adjustment", "keep")
        current_price = current_products.get(product_id, {}).get('price', 'N/A')
        
        print(f"Product: {product_data['name']}")
        print(f"Current price: €{current_price}")
        print(f"Current adjustment: {current_adjustment}")
        
        new_adjustment = input("New adjustment (or press Enter to keep): ").strip()
        
        if new_adjustment:
            if new_adjustment == "keep":
                product_data["adjustment"] = "keep"
            else:
                try:
                    product_data["adjustment"] = float(new_adjustment)
                except ValueError:
                    print("Invalid adjustment, keeping current value")
        
        print()
    
    # Configure delay
    current_delay = config_manager.get_delay_days()
    print(f"Current delay between updates: {current_delay} days")
    new_delay = input("New delay in days (0 = always update): ").strip()
    
    if new_delay:
        try:
            config_manager.config["settings"]["delay_days"] = int(new_delay)
        except ValueError:
            print("Invalid delay, keeping current value")
    
    config_manager.save_config()
    print(f"\n✓ Configuration saved to {config_manager.config_path}")

if __name__ == "__main__":
    configure_products()