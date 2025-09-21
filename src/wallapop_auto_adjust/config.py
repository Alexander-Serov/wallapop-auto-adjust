import json
import os
from datetime import datetime
from typing import Dict, Any, List


class ConfigManager:
    def __init__(self, config_path: str = "products_config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {"products": {}, "settings": {"delay_days": 1}}

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def update_products(self, products: List[Dict[str, Any]]):
        """Update config with new products, preserving existing settings"""
        for product in products:
            product_id = product['id']
            if product_id not in self.config["products"]:
                # Convert timestamp to ISO format if needed
                last_mod = product.get('last_modified')
                if isinstance(last_mod, (int, float)):
                    last_mod = datetime.fromtimestamp(last_mod / 1000 if last_mod > 1e10 else last_mod).astimezone().isoformat()

                self.config["products"][product_id] = {
                    "name": product['name'],
                    "adjustment": "keep",
                    "last_modified": last_mod
                }
            else:
                # Update name and last_modified in case they changed
                self.config["products"][product_id]["name"] = product['name']
                if product.get('last_modified'):
                    last_mod = product['last_modified']
                    if isinstance(last_mod, (int, float)):
                        last_mod = datetime.fromtimestamp(last_mod / 1000 if last_mod > 1e10 else last_mod).astimezone().isoformat()
                    self.config["products"][product_id]["last_modified"] = last_mod

    def remove_sold_products(self, current_products: List[Dict[str, Any]]) -> List[str]:
        """Remove products from config that are no longer in the current product list (i.e., sold)
        
        Args:
            current_products: List of products currently returned by API
            
        Returns:
            List of product names that were removed
        """
        # Get current product IDs from API
        current_product_ids = {product['id'] for product in current_products}
        
        # Find products in config that are no longer in API response
        config_product_ids = set(self.config["products"].keys())
        sold_product_ids = config_product_ids - current_product_ids
        
        removed_products = []
        for product_id in sold_product_ids:
            product_name = self.config["products"][product_id].get("title", f"Product {product_id}")
            removed_products.append(product_name)
            del self.config["products"][product_id]
        
        return removed_products

    def get_product_config(self, product_id: str) -> Dict[str, Any]:
        return self.config["products"].get(product_id, {})

    def update_last_modified(self, product_id: str, date: str = None):
        if date is None:
            date = datetime.now().astimezone().isoformat()
        if product_id in self.config["products"]:
            self.config["products"][product_id]["last_modified"] = date
            self.save_config()

    def get_delay_days(self) -> int:
        return self.config["settings"].get("delay_days", 1)
