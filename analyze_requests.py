#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import json
import time

class WallapopAnalyzer:
    def __init__(self):
        self.setup_driver()
        self.requests = []
    
    def setup_driver(self):
        options = Options()
        options.add_argument("--enable-network-service-logging")
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        
        # Enable logging
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        self.driver = webdriver.Chrome(options=options)
    
    def capture_network_requests(self):
        """Capture all network requests"""
        logs = self.driver.get_log('performance')
        for log in logs:
            message = json.loads(log['message'])
            if message['message']['method'] == 'Network.responseReceived':
                url = message['message']['params']['response']['url']
                if 'wallapop' in url:
                    self.requests.append({
                        'url': url,
                        'method': message['message']['params']['response'].get('method', 'GET'),
                        'headers': message['message']['params']['response'].get('headers', {}),
                        'timestamp': log['timestamp']
                    })
    
    def analyze_login(self):
        print("=== ANALYZING LOGIN PROCESS ===")
        print("1. Navigate to https://es.wallapop.com")
        print("2. Click login and enter credentials")
        print("3. Press ENTER when login is complete")
        
        self.driver.get("https://es.wallapop.com")
        input("Press ENTER after completing login...")
        
        self.capture_network_requests()
        
        # Filter login-related requests
        login_requests = [r for r in self.requests if any(keyword in r['url'].lower() 
                         for keyword in ['login', 'auth', 'session', 'token'])]
        
        print(f"\nFound {len(login_requests)} login-related requests:")
        for req in login_requests:
            print(f"- {req['method']} {req['url']}")
        
        return login_requests
    
    def analyze_products_listing(self):
        print("\n=== ANALYZING PRODUCTS LISTING ===")
        print("1. Navigate to your products page")
        print("2. Press ENTER when products are loaded")
        
        # Clear previous requests
        self.requests = []
        
        input("Press ENTER after navigating to products page...")
        
        self.capture_network_requests()
        
        # Filter product-related requests
        product_requests = [r for r in self.requests if any(keyword in r['url'].lower() 
                           for keyword in ['product', 'item', 'listing', 'user'])]
        
        print(f"\nFound {len(product_requests)} product-related requests:")
        for req in product_requests:
            print(f"- {req['method']} {req['url']}")
        
        return product_requests
    
    def analyze_price_update(self):
        print("\n=== ANALYZING PRICE UPDATE ===")
        print("1. Edit a product price")
        print("2. Save the changes")
        print("3. Press ENTER when update is complete")
        
        # Clear previous requests
        self.requests = []
        
        input("Press ENTER after updating a product price...")
        
        self.capture_network_requests()
        
        # Filter update-related requests
        update_requests = [r for r in self.requests if any(keyword in r['url'].lower() 
                          for keyword in ['update', 'edit', 'put', 'patch', 'product'])]
        
        print(f"\nFound {len(update_requests)} update-related requests:")
        for req in update_requests:
            print(f"- {req['method']} {req['url']}")
        
        return update_requests
    
    def save_analysis(self, login_reqs, product_reqs, update_reqs):
        analysis = {
            'login_requests': login_reqs,
            'product_requests': product_reqs,
            'update_requests': update_reqs,
            'timestamp': time.time()
        }
        
        with open('wallapop_analysis.json', 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\nAnalysis saved to wallapop_analysis.json")
    
    def close(self):
        self.driver.quit()

def main():
    analyzer = WallapopAnalyzer()
    
    try:
        login_reqs = analyzer.analyze_login()
        product_reqs = analyzer.analyze_products_listing()
        update_reqs = analyzer.analyze_price_update()
        
        analyzer.save_analysis(login_reqs, product_reqs, update_reqs)
        
        print("\n=== ANALYSIS COMPLETE ===")
        print("Check wallapop_analysis.json for detailed request information")
        
    finally:
        analyzer.close()

if __name__ == "__main__":
    main()