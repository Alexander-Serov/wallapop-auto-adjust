#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import json
import time

class PriceUpdateAnalyzer:
    def __init__(self):
        self.setup_driver()
        self.requests = []
    
    def setup_driver(self):
        options = Options()
        options.add_argument("--enable-network-service-logging")
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        self.driver = webdriver.Chrome(options=options)
    
    def capture_network_requests(self):
        """Capture all network requests"""
        logs = self.driver.get_log('performance')
        for log in logs:
            message = json.loads(log['message'])
            if message['message']['method'] in ['Network.requestWillBeSent', 'Network.responseReceived']:
                params = message['message']['params']
                if 'wallapop' in params.get('request', params.get('response', {})).get('url', ''):
                    self.requests.append({
                        'method': message['message']['method'],
                        'params': params,
                        'timestamp': log['timestamp']
                    })
    
    def analyze_price_update(self):
        print("=== PRICE UPDATE ANALYSIS ===")
        print("1. Navigate to Wallapop and login")
        print("2. Go to one of your products")
        print("3. Edit the price and save")
        print("4. Press ENTER when done")
        
        self.driver.get("https://es.wallapop.com")
        input("Press ENTER after completing price update...")
        
        self.capture_network_requests()
        
        # Filter for potential update requests
        update_requests = []
        for req in self.requests:
            if req['method'] == 'Network.requestWillBeSent':
                url = req['params']['request']['url']
                method = req['params']['request']['method']
                
                # Look for PUT, POST, PATCH requests to item endpoints
                if (method in ['PUT', 'POST', 'PATCH'] and 
                    'api' in url and 
                    ('item' in url or 'product' in url)):
                    update_requests.append({
                        'method': method,
                        'url': url,
                        'headers': req['params']['request'].get('headers', {}),
                        'postData': req['params']['request'].get('postData', ''),
                        'timestamp': req['timestamp']
                    })
        
        print(f"\nFound {len(update_requests)} potential update requests:")
        for req in update_requests:
            print(f"- {req['method']} {req['url']}")
            if req['postData']:
                print(f"  Data: {req['postData'][:200]}...")
        
        # Save analysis
        with open('price_update_analysis.json', 'w') as f:
            json.dump(update_requests, f, indent=2)
        
        print(f"\nAnalysis saved to price_update_analysis.json")
        self.driver.quit()

if __name__ == "__main__":
    analyzer = PriceUpdateAnalyzer()
    analyzer.analyze_price_update()