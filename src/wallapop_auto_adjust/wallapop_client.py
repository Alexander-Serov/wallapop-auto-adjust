import requests
from typing import List, Dict, Any
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from wallapop_auto_adjust.session_manager import SessionManager

class WallapopClient:
    def __init__(self):
        self.session_manager = SessionManager()
        self.session = self.session_manager.session
        self.base_url = "https://api.wallapop.com"
        self.web_url = "https://es.wallapop.com"
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Origin': 'https://es.wallapop.com',
            'Referer': 'https://es.wallapop.com/app/catalog/published',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        })
        
        self.driver = None
    
    def login(self, email: str, password: str) -> bool:
        """Login with session persistence"""
        # Try to load existing session first
        if self.session_manager.load_session():
            print("Loaded saved session, testing...")
            if self._test_auth():
                print("✓ Existing session is valid")
                return True
            else:
                print("Saved session expired, need fresh login")
        
        # Need fresh login
        return self._fresh_login(email, password)
    
    def _test_auth(self) -> bool:
        """Test if current session is authenticated"""
        try:
            # Test web session first
            response = self.session.get(f"{self.web_url}/api/auth/session")
            return response.status_code == 200
        except:
            return False
    
    def _fresh_login(self, email: str, password: str) -> bool:
        """Perform fresh browser login"""
        try:
            options = Options()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            self.driver = webdriver.Chrome(options=options)
            
            print("Opening browser for login...")
            self.driver.get(f"{self.web_url}/auth/signin")
            time.sleep(3)
            
            # Enter email
            try:
                email_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
                )
                email_input.clear()
                email_input.send_keys(email)
                print(f"Entered email: {email}")
            except:
                print("Could not find email input")
            
            print("Complete login manually (captcha, SMS, etc.)...")
            print("Script will continue automatically when login is detected...")
            
            # Wait for login completion - check multiple indicators
            def login_completed(driver):
                try:
                    current_url = driver.current_url
                    # Check for successful login indicators
                    return any([
                        "catalog" in current_url,
                        "app/you" in current_url,
                        "/app/" in current_url,
                        len(driver.find_elements(By.CSS_SELECTOR, "[data-testid*='user'], .user-menu, .profile-menu")) > 0
                    ])
                except:
                    return False
            
            WebDriverWait(self.driver, 300).until(login_completed)  # 5 minute timeout
            
            print("Login detected! Extracting session...")
            
            # Navigate to a page that makes API calls to capture headers
            self.driver.get(f"{self.web_url}/app/catalog/published")
            time.sleep(3)
            
            # Call federated session endpoint like in the analysis
            self.driver.get(f"{self.web_url}/api/auth/federated-session")
            time.sleep(2)
            
            # Extract cookies
            cookies = {}
            for cookie in self.driver.get_cookies():
                cookies[cookie['name']] = cookie['value']
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            # Save session for future use
            self.session_manager.save_session(cookies)
            
            self.driver.quit()
            
            # Test the extracted session
            if self._test_auth():
                print("✓ Session extracted successfully")
                return True
            else:
                print("✗ Session extraction failed")
                return False
                
        except Exception as e:
            print(f"Login failed: {e}")
            if self.driver:
                self.driver.quit()
            return False
    
    def get_user_products(self) -> List[Dict[str, Any]]:
        """Get current user's products"""
        try:
            # Get access token from cookies
            access_token = self.session.cookies.get('accessToken')
            if not access_token:
                print("No access token found in cookies")
                return []
            
            # Add Authorization header
            headers = {'Authorization': f'Bearer {access_token}'}
            
            response = self.session.get(f"{self.base_url}/api/v3/user/items", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                products = []
                
                items = data.get('items', data.get('data', []))
                
                for item in items:
                    # Handle price field which might be a dict
                    price_data = item.get('price', 0)
                    if isinstance(price_data, dict):
                        price = float(price_data.get('amount', 0))
                        currency = price_data.get('currency', 'EUR')
                    else:
                        price = float(price_data)
                        currency = item.get('currency', 'EUR')
                    
                    products.append({
                        'id': item.get('id'),
                        'name': item.get('title', item.get('name', '')),
                        'price': price,
                        'currency': currency,
                        'status': item.get('status'),
                        'last_modified': item.get('modified_date', item.get('updated_at'))
                    })
                
                return products
            else:
                print(f"API failed: {response.status_code} - {response.text[:200]}")
                if response.status_code == 401:
                    self.session_manager.clear_session()
                return []
                
        except Exception as e:
            print(f"Error getting products: {e}")
            return []
    
    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Get detailed product information for editing"""
        try:
            access_token = self.session.cookies.get('accessToken')
            if not access_token:
                return {}
            
            # Use same headers as in the captured request
            mpid = self.session.cookies.get('MPID', '')
            device_id = self.session.cookies.get('device_id', '')
            
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'DeviceOS': '0',
                'MPID': mpid,
                'Referer': 'https://es.wallapop.com/',
                'X-AppVersion': '89340',
                'X-DeviceID': device_id,
                'X-DeviceOS': '0'
            }
            
            response = self.session.get(f"{self.base_url}/api/v3/items/{product_id}/edit?language=es", headers=headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get product details: {response.status_code} - {response.text[:200]}")
                return {}
                
        except Exception as e:
            print(f"Error getting product details: {e}")
            return {}
    
    def update_product_price(self, product_id: str, new_price: float) -> bool:
        """Update product price"""
        try:
            access_token = self.session.cookies.get('accessToken')
            if not access_token:
                print("No access token found")
                return False
            
            # Get product details in edit format
            product_details = self.get_product_details(product_id)
            if not product_details:
                print("Could not get product details")
                return False
            
            # Use exact headers from captured price update request
            mpid = self.session.cookies.get('MPID', '')
            device_id = self.session.cookies.get('device_id', '')
            
            # First call the components endpoint like in the captured request
            components_headers = {
                'Accept': 'application/json, text/plain, */*',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'DeviceOS': '0',
                'MPID': mpid,
                'Referer': 'https://es.wallapop.com/',
                'X-AppVersion': '89340',
                'X-DeviceID': device_id,
                'X-DeviceOS': '0'
            }
            
            components_payload = {
                'fields': {
                    'id': product_id,
                    'category_leaf_id': product_details.get('taxonomy', [{}])[-1].get('id', '')
                },
                'mode': {
                    'action': 'edit',
                    'id': f'{product_id}-edit-session'
                }
            }
            
            components_response = self.session.post(
                f"{self.base_url}/api/v3/items/upload/components",
                json=components_payload,
                headers=components_headers
            )
            
            print(f"Components response: {components_response.status_code}")
            if components_response.status_code >= 400:
                print(f"Components error: {components_response.text}")
                return False
            
            # Now do the actual update
            headers = {
                'Accept': 'application/vnd.upload-v2+json',
                'Accept-Language': 'es,ca-ES;q=0.9,ca;q=0.8',
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'DeviceOS': '0',
                'MPID': mpid,
                'Referer': 'https://es.wallapop.com/',
                'X-AppVersion': '89340',
                'X-DeviceID': device_id,
                'X-DeviceOS': '0'
            }
            
            payload = {
                'attributes': {
                    'title': product_details.get('title', {}).get('original', ''),
                    'description': product_details.get('description', {}).get('original', ''),
                    'condition': product_details.get('type_attributes', {}).get('condition', {}).get('value', 'as_good_as_new')
                },
                'category_leaf_id': product_details.get('taxonomy', [{}])[-1].get('id', ''),
                'price': {
                    'cash_amount': new_price,
                    'currency': 'EUR',
                    'apply_discount': False
                },
                'location': {
                    'latitude': product_details.get('location', {}).get('latitude', 0),
                    'longitude': product_details.get('location', {}).get('longitude', 0),
                    'approximated': False
                },
                'delivery': {
                    'allowed_by_user': product_details.get('shipping', {}).get('user_allows_shipping', True),
                    'max_weight_kg': int(float(product_details.get('type_attributes', {}).get('up_to_kg', {}).get('value', '1.0')))
                }
            }
            
            response = self.session.put(
                f"{self.base_url}/api/v3/items/{product_id}",
                json=payload,
                headers=headers
            )
            
            if response.status_code >= 400:
                print(f"Update response: {response.status_code}")
                print(f"Full error response: {response.text}")
                print(f"Payload sent: {json.dumps(payload, indent=2)}")
            else:
                print(f"✓ Price updated successfully to €{new_price}")
            
            return response.status_code in [200, 204]
            
        except Exception as e:
            print(f"Error updating product price: {e}")
            return False
