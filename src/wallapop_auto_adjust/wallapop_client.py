import requests
from typing import List, Dict, Any
import time
import json
import random
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from wallapop_auto_adjust.session_manager import SessionManager

# Constants
LOGIN_TIMEOUT_SECONDS = 300
BROWSER_CHECK_INTERVAL_SECONDS = 2
SESSION_DIR = ".tmp"
FINGERPRINT_FILE = "browser_fingerprint.json"

# Chrome versions from the last 6 months
CHROME_VERSIONS = [
    "119.0.0.0", "120.0.0.0", "121.0.0.0", 
    "122.0.0.0", "123.0.0.0", "124.0.0.0", "125.0.0.0"
]

# macOS versions (adjust based on your system)
OS_VERSIONS = [
    "10_15_7", "11_7_10", "12_7_4", 
    "13_6_7", "14_6_1", "15_0_0"
]

WEBKIT_VERSIONS = ["537.36", "605.1.15"]

# Common screen resolutions
COMMON_RESOLUTIONS = [
    (1920, 1080), (1366, 768), (1440, 900), 
    (1536, 864), (1680, 1050), (2560, 1440),
    (1728, 1117), (1512, 982)
]

# Platform options
PLATFORMS = ['MacIntel', 'Win32', 'Linux x86_64']

# Language options
LANGUAGE_OPTIONS = [
    ['en-US', 'en'],
    ['es-ES', 'es', 'en'], 
    ['ca-ES', 'es', 'en']
]

# Timezone offset options
TIMEZONE_OFFSETS = [-480, -420, -360, -300, -240, -180, -120, -60, 0, 60, 120]

# Optional Chrome switches for randomization
OPTIONAL_CHROME_SWITCHES = [
    "--disable-gpu",
    "--disable-extensions", 
    "--disable-plugins-discovery",
    "--allow-running-insecure-content",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding"
]

# Random selection range for chrome switches (60-80%)
CHROME_SWITCHES_MIN_RATIO = 0.6
CHROME_SWITCHES_MAX_RATIO = 0.8

# Human typing speed range (seconds)
HUMAN_TYPE_MIN_DELAY = 0.05
HUMAN_TYPE_MAX_DELAY = 0.2

# Random delay ranges (seconds)
NAVIGATION_DELAY_MIN = 1.0
NAVIGATION_DELAY_MAX = 3.0
PAGE_LOAD_DELAY_MIN = 2.0
PAGE_LOAD_DELAY_MAX = 4.0

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
        
        # Set session directory for fingerprint persistence
        self.session_dir = Path(SESSION_DIR)
        self.session_dir.mkdir(exist_ok=True)  # Create directory if it doesn't exist
    
    def _generate_random_user_agent(self):
        """Generate a realistic, random user agent"""
        chrome_version = random.choice(CHROME_VERSIONS)
        os_version = random.choice(OS_VERSIONS)
        webkit_version = random.choice(WEBKIT_VERSIONS)
        
        return f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_version}) AppleWebKit/{webkit_version} (KHTML, like Gecko) Chrome/{chrome_version} Safari/{webkit_version}"

    def _get_random_viewport(self):
        """Get random but realistic viewport dimensions"""
        return random.choice(COMMON_RESOLUTIONS)

    def _get_session_fingerprint(self):
        """Maintain consistent fingerprint for this session"""
        fingerprint_file = self.session_dir / FINGERPRINT_FILE
        
        if fingerprint_file.exists():
            with open(fingerprint_file) as f:
                return json.load(f)
        
        # Generate new fingerprint for this session
        fingerprint = {
            'user_agent': self._generate_random_user_agent(),
            'viewport': self._get_random_viewport(),
            'platform': random.choice(PLATFORMS),
            'languages': random.choice(LANGUAGE_OPTIONS),
            'timezone_offset': random.choice(TIMEZONE_OFFSETS)
        }
        
        # Save for this session
        with open(fingerprint_file, 'w') as f:
            json.dump(fingerprint, f)
        
        return fingerprint

    def _generate_fingerprint_script(self, fingerprint):
        """Generate randomized browser fingerprint injection script"""
        width, height = fingerprint['viewport']
        
        fingerprint_script = f"""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {{
                get: () => undefined
            }});
            
            // Randomize navigator properties
            Object.defineProperty(navigator, 'languages', {{
                get: () => {json.dumps(fingerprint['languages'])}
            }});
            
            Object.defineProperty(navigator, 'platform', {{
                get: () => '{fingerprint['platform']}'
            }});
            
            // Randomize screen properties
            Object.defineProperty(screen, 'width', {{
                get: () => {width}
            }});
            Object.defineProperty(screen, 'height', {{
                get: () => {height}
            }});
            Object.defineProperty(screen, 'availWidth', {{
                get: () => {width}
            }});
            Object.defineProperty(screen, 'availHeight', {{
                get: () => {height - random.randint(30, 80)}
            }});
            
            // Add realistic plugin fingerprint
            Object.defineProperty(navigator, 'plugins', {{
                get: () => {{
                    return [
                        {{"name": "Chrome PDF Plugin", "length": {random.randint(1, 3)}}},
                        {{"name": "Chrome PDF Viewer", "length": {random.randint(1, 3)}}},
                        {{"name": "Native Client", "length": {random.randint(1, 2)}}}
                    ];
                }}
            }});
            
            // Randomize timing slightly
            const originalPerformanceNow = performance.now;
            performance.now = function() {{
                return originalPerformanceNow.call(this) + {random.uniform(-0.5, 0.5)};
            }};
            
            // Randomize timezone
            Date.prototype.getTimezoneOffset = function() {{
                return {fingerprint['timezone_offset']};
            }};
        """
        
        return fingerprint_script

    def _human_like_type(self, element, text):
        """Type text with human-like timing"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(HUMAN_TYPE_MIN_DELAY, HUMAN_TYPE_MAX_DELAY))

    def _add_human_behavior(self):
        """Add subtle human-like behaviors"""
        # Random small mouse movements
        try:
            actions = ActionChains(self.driver)
            actions.move_by_offset(
                random.randint(-10, 10), 
                random.randint(-10, 10)
            ).perform()
        except:
            pass  # Ignore if this fails

    def _manual_cookie_login(self) -> bool:
        """Manual cookie extraction from user's browser"""
        print("\n=== MANUAL COOKIE EXTRACTION ===")
        print("Automated login failed. Let's extract cookies manually.")
        print("\n1. Open Chrome and go to https://es.wallapop.com")
        print("2. Log in normally (this works with 2FA, captchas, etc.)")
        print("3. Open Developer Tools (F12)")
        print("4. Go to Application tab > Cookies > https://es.wallapop.com")
        print("5. Look for these cookies:")
        print("   - accessToken (required)")
        print("   - MPID (optional)")
        
        access_token = input("\nEnter accessToken value: ").strip()
        if not access_token:
            print("accessToken is required for authentication")
            return False
            
        mpid = input("Enter MPID value (press Enter if not found): ").strip()
        
        # Set cookies in session exactly like the automated version
        self.session.cookies.set('accessToken', access_token)
        if mpid:
            self.session.cookies.set('MPID', mpid)
        
        # Save session
        cookies = {
            'accessToken': access_token,
            'MPID': mpid
        }
        self.session_manager.save_session(cookies)
        
        # Test the session
        if self._test_auth():
            print("✓ Manual cookie extraction successful!")
            return True
        else:
            print("✗ Cookies don't seem to work. Please try again or check if you're still logged in.")
            return False

    def login(self, email: str, password: str) -> bool:
        """Login with session persistence and fallback options"""
        # Try to load existing session first
        if self.session_manager.load_session():
            print("Loaded saved session, testing...")
            if self._test_auth():
                print("✓ Existing session is valid")
                return True
            else:
                print("Saved session expired, need fresh login")
        
        # Try automated login first
        print("Attempting automated login with randomized fingerprint...")
        if self._fresh_login(email, password):
            return True
        
        # Fall back to manual cookie extraction
        print("\nAutomated login failed. This might be due to:")
        print("- Enhanced bot detection")
        print("- Changed page structure") 
        print("- Captcha or 2FA requirements")
        
        choice = input("\nTry manual cookie extraction? (Y/n): ").lower().strip()
        if choice in ['', 'y', 'yes']:  # Default to 'y' when user presses Enter
            return self._manual_cookie_login()
        
        print("Login failed. Please check your credentials or try again later.")
        return False
    
    def _test_auth(self) -> bool:
        """Test if current session is authenticated"""
        try:
            # Test web session first
            response = self.session.get(f"{self.web_url}/api/auth/session")
            return response.status_code == 200
        except:
            return False
    
    def _fresh_login(self, email: str, password: str) -> bool:
        """Perform fresh browser login with randomized fingerprint"""
        try:
            # Get session-consistent fingerprint
            fingerprint = self._get_session_fingerprint()
            
            options = Options()
            
            # Core anti-detection (these are standard)
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--no-sandbox")
            
            # Ensure captcha compatibility
            options.add_argument("--enable-javascript")  # Ensure JS is enabled for captchas
            
            # Use session-consistent user agent
            options.add_argument(f"--user-agent={fingerprint['user_agent']}")
            
            # Use session-consistent window size
            width, height = fingerprint['viewport']
            options.add_argument(f"--window-size={width},{height}")
            
            # Randomized Chrome switches (sometimes include, sometimes don't)
            # Randomly include 60-80% of optional switches
            selected_switches = random.sample(
                OPTIONAL_CHROME_SWITCHES, 
                k=random.randint(
                    int(len(OPTIONAL_CHROME_SWITCHES) * CHROME_SWITCHES_MIN_RATIO), 
                    int(len(OPTIONAL_CHROME_SWITCHES) * CHROME_SWITCHES_MAX_RATIO)
                )
            )
            
            for switch in selected_switches:
                options.add_argument(switch)
            
            # Always exclude these
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Randomized preferences - but ensure images are always enabled for captchas
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.managed_default_content_settings.images": 1  # Always enable images for captchas
            }
            
            # Sometimes add additional random prefs
            if random.random() > 0.5:
                prefs["profile.default_content_settings.popups"] = 0
            if random.random() > 0.7:
                prefs["profile.default_content_setting_values.geolocation"] = random.choice([1, 2])
                
            options.add_experimental_option("prefs", prefs)
            
            print(f"Starting browser with fingerprint: {fingerprint['user_agent'][:50]}...")
            self.driver = webdriver.Chrome(options=options)
            
            # Apply randomized fingerprint
            fingerprint_script = self._generate_fingerprint_script(fingerprint)
            self.driver.execute_script(fingerprint_script)
            
            # Random delay before navigation
            time.sleep(random.uniform(NAVIGATION_DELAY_MIN, NAVIGATION_DELAY_MAX))
            
            print("Navigating to Wallapop login page...")
            self.driver.get("https://es.wallapop.com/auth/signin")
            
            # Add human behavior
            self._add_human_behavior()
            time.sleep(random.uniform(PAGE_LOAD_DELAY_MIN, PAGE_LOAD_DELAY_MAX))
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            print("Login page loaded. Please complete login manually...")
            print("The script will detect when login is successful and continue automatically.")
            
            # Check if we're already on the login form or need to find it
            try:
                # Try to find email field to see if we're on the login form
                email_field = self.driver.find_elements(By.XPATH, "//input[@type='email' or @name='email' or contains(@placeholder, 'email')]")
                
                if email_field:
                    print("Found email field. Please enter your login credentials manually.")
                    print("✓ You can handle 2FA, captchas, etc. as needed")
                    # Pre-fill email if found
                    try:
                        email_field[0].clear()
                        email_field[0].send_keys(email)
                        print(f"Pre-filled email: {email}")
                    except:
                        print("Could not pre-fill email, please enter manually")
                else:
                    print("Login form not immediately visible. Please navigate to login if needed.")
                
                print("Complete login manually (captcha, SMS, etc.)...")
                print("Script will continue automatically when login is detected...")
                print("You can also close the browser to skip to manual cookie extraction.")
                
                # Wait for login completion or browser closure
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
                
                def is_browser_alive(driver):
                    try:
                        # Try to get current URL - this will fail if browser is closed
                        driver.current_url
                        return True
                    except:
                        return False
                
                # Custom wait loop that checks for both login completion and browser closure
                max_wait_time = LOGIN_TIMEOUT_SECONDS  # 5 minutes
                check_interval = BROWSER_CHECK_INTERVAL_SECONDS   # Check every 2 seconds
                elapsed_time = 0
                
                while elapsed_time < max_wait_time:
                    if not is_browser_alive(self.driver):
                        print("Browser was closed. Moving to manual cookie extraction...")
                        return False  # This will trigger the fallback
                    
                    if login_completed(self.driver):
                        break
                    
                    time.sleep(check_interval)
                    elapsed_time += check_interval
                
                # Check one more time if we exited due to timeout
                if elapsed_time >= max_wait_time:
                    print("Login timeout reached. Moving to manual cookie extraction...")
                    return False
                
                if not is_browser_alive(self.driver):
                    print("Browser was closed during check. Moving to manual cookie extraction...")
                    return False
                
                print("Login detected! Extracting session...")
                
                # Check if browser is still alive before session extraction
                if not is_browser_alive(self.driver):
                    print("Browser was closed after login detection. Moving to manual cookie extraction...")
                    return False
                
                # Navigate to a page that makes API calls to capture headers
                try:
                    self.driver.get("https://es.wallapop.com/app/catalog/published")
                    time.sleep(3)
                    
                    # Call federated session endpoint like in the analysis
                    self.driver.get("https://es.wallapop.com/api/auth/federated-session")
                    time.sleep(2)
                except:
                    print("Browser closed during session extraction. Moving to manual cookie extraction...")
                    return False
                
                # Extract cookies
                cookies = {}
                try:
                    for cookie in self.driver.get_cookies():
                        cookies[cookie['name']] = cookie['value']
                        self.session.cookies.set(cookie['name'], cookie['value'])
                except:
                    print("Browser closed during cookie extraction. Moving to manual cookie extraction...")
                    return False
                
                # Save session for future use
                self.session_manager.save_session(cookies)
                
                # Close browser after successful extraction
                try:
                    self.driver.quit()
                except:
                    pass  # Browser might already be closed
                
                # Test the extracted session
                if self._test_auth():
                    print("✓ Session extracted successfully")
                    return True
                else:
                    print("✗ Session extraction failed")
                    return False
                    
            except Exception as e:
                print(f"Error during login process: {e}")
                if self.driver:
                    self.driver.quit()
                return False
                
        except Exception as e:
            print(f"Error setting up browser: {e}")
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
