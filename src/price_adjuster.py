from datetime import datetime, timedelta
from dateutil.parser import parse
from typing import Dict, Any
import math

class PriceAdjuster:
    def __init__(self, wallapop_client, config_manager):
        self.client = wallapop_client
        self.config = config_manager
    
    def should_update_price(self, product_id: str) -> bool:
        """Check if enough time has passed since last update"""
        delay_days = self.config.get_delay_days()
        if delay_days == 0:
            return True
        
        product_config = self.config.get_product_config(product_id)
        last_modified = product_config.get("last_modified")
        
        if not last_modified:
            return True
        
        try:
            # Handle different date formats
            if isinstance(last_modified, (int, float)):
                # Unix timestamp
                last_date = datetime.fromtimestamp(last_modified / 1000 if last_modified > 1e10 else last_modified)
            else:
                # ISO string date
                last_date = datetime.fromisoformat(str(last_modified).replace('Z', '+00:00'))
            
            days_passed = (datetime.now().astimezone() - last_date).days
            return days_passed >= delay_days
        except:
            # If date parsing fails, allow update
            return True
    
    def calculate_new_price(self, current_price: float, adjustment: Any) -> float:
        """Calculate new price based on adjustment"""
        if adjustment == "keep":
            return current_price
        
        new_price = current_price * float(adjustment)
        new_price = round(new_price, 2)
        
        # Enforce minimum price of €1
        if new_price < 1.0:
            new_price = 1.0
        
        return new_price
    

    
    def get_user_adjustment(self, product_name: str, current_price: float, default_adjustment: Any) -> Any:
        """Get adjustment decision from user"""
        print(f"\n→ {product_name} (€{current_price:.2f})")
        
        if default_adjustment == "keep":
            default_text = "keep"
        else:
            new_price = self.calculate_new_price(current_price, default_adjustment)
            default_text = f"{default_adjustment} (→ €{new_price:.2f})"
        
        response = input(f"  Action [default: {default_text}]: ").strip()
        
        if not response:
            return default_adjustment
        
        if response.lower() in ['keep', 'k']:
            return "keep"
        
        try:
            return float(response)
        except ValueError:
            print("  Invalid input, using default")
            return default_adjustment
    
    def adjust_product_price(self, product: Dict[str, Any]) -> bool:
        """Adjust single product price"""
        product_id = product['id']
        product_name = product['name']
        current_price = product['price']
        
        if not self.should_update_price(product_id):
            print(f"Skipping {product_name} (€{current_price:.2f}) - delay period not met")
            return False
        
        product_config = self.config.get_product_config(product_id)
        default_adjustment = product_config.get("adjustment", "keep")
        
        # Get user decision
        adjustment = self.get_user_adjustment(product_name, current_price, default_adjustment)
        
        # Update config if user changed the adjustment
        if adjustment != default_adjustment:
            self.config.config["products"][product_id]["adjustment"] = adjustment
            self.config.save_config()
        
        if adjustment == "keep":
            print(f"  Keeping current price")
            return False
        
        new_price = self.calculate_new_price(current_price, adjustment)
        
        if new_price == current_price:
            print(f"  No change needed")
            return False
        
        print(f"  Current: €{current_price:.2f} → New: €{new_price:.2f}")
        confirm = input("  Apply this change? (y/n) [y]: ").lower().strip()
        
        if confirm in ['y', 'yes', '']:
            success = self.client.update_product_price(product_id, new_price)
            if success:
                self.config.update_last_modified(product_id)  # This now auto-saves
                
                # Switch to "keep" if price hit minimum limit
                if new_price == 1.0 and current_price * float(adjustment) < 1.0:
                    self.config.config["products"][product_id]["adjustment"] = "keep"
                    self.config.save_config()
                    print(f"  ✓ Updated: €{current_price:.2f} → €{new_price:.2f} (switched to 'keep' - minimum reached)")
                else:
                    print(f"  ✓ Updated: €{current_price:.2f} → €{new_price:.2f}")
                return True
            else:
                print(f"  ✗ Failed to update")
        else:
            print(f"  Skipped - user declined")
        
        return False