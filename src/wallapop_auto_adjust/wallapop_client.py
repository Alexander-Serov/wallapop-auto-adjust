import requests
from typing import List, Dict, Any, Optional
import json
import sys
import os
import random
from pathlib import Path
from wallapop_auto_adjust.session_persistence import (
    SessionPersistenceManager,
    SessionManager as _CompatSessionManager,
)


"""
Modern Wallapop API client using persistent session management.

Backwards-compatibility notes:
- Exposes a `SessionManager` symbol in this module namespace to satisfy legacy tests that patch it.
- Provides compatibility methods: login, _fresh_login, _manual_cookie_login, _test_auth, and _get_session_fingerprint.
  These are lightweight shims around the modern SessionPersistenceManager and are primarily for tests.
"""

# Re-export for tests that patch wallapop_auto_adjust.wallapop_client.SessionManager
SessionManager = _CompatSessionManager


class WallapopClient:
    """Modern Wallapop API client using persistent session management"""

    def __init__(self):
        """Initialize the Wallapop client with modern session management"""
        # Use the compatibility SessionManager so tests can patch this symbol
        self.session_manager = SessionManager()
        self.base_url = "https://api.wallapop.com"
        self.web_url = "https://es.wallapop.com"
        # Lazily load session when needed; do not raise during __init__ (tests patch behavior)
        self.session = None
        # Use the same home session directory as SessionPersistenceManager (no env override)
        self.session_dir = Path.home() / ".wallapop-auto-adjust"
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.fingerprint_file = self.session_dir / "fingerprint.json"
        # Do not set headers yet; headers are applied when the session is actually loaded

    def _make_authenticated_request(
        self, method: str, url: str, **kwargs
    ) -> Optional[requests.Response]:
        """Make an authenticated request using the session manager"""
        return self.session_manager.make_authenticated_request(method, url, **kwargs)

    # -----------------------------
    # Backwards-compatible helpers
    # -----------------------------
    def _ensure_session(self) -> None:
        """Ensure the underlying requests.Session is initialized and headers applied."""
        if not self.session_manager.session:
            # Try to load; ignore return here as callers will handle auth state
            self.session_manager.load_session()
        self.session = self.session_manager.session
        if self.session and "User-Agent" not in self.session.headers:
            # Set common headers for all requests once
            self.session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Origin": "https://es.wallapop.com",
                    "Referer": "https://es.wallapop.com/app/catalog/published",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-site",
                }
            )

    def _get_session_fingerprint(self) -> Dict[str, Any]:
        """Generate or load a simple browser fingerprint for the session.

        Returns a dict with keys: user_agent, viewport(list), platform, languages(list), timezone_offset(int)
        """
        try:
            if self.fingerprint_file.exists():
                with open(self.fingerprint_file, "r") as f:
                    return json.load(f)
        except Exception:
            pass

        # Randomized components (values chosen will be controlled by tests via random.choice patches)
        chrome_versions = ["120.0.0.0", "121.0.6167.85", "122.0.6261.70"]
        os_versions = ["11_7_10", "13_5_2", "12_6_1"]
        webkit_versions = ["537.36", "605.1.15"]
        viewports = [(1920, 1080), (1536, 960), (2560, 1440)]
        platforms = ["MacIntel", "Win32", "Linux x86_64"]
        languages_list = [["en-US", "en"], ["es-ES", "es"], ["fr-FR", "fr"]]
        tz_offsets = [-300, 60, 0]

        chrome = random.choice(chrome_versions)
        os_ver = random.choice(os_versions)
        webkit = random.choice(webkit_versions)
        viewport = random.choice(viewports)
        platform = random.choice(platforms)
        languages = random.choice(languages_list)
        tz_offset = random.choice(tz_offsets)

        user_agent = (
            f"Mozilla/5.0 (Macintosh; Intel Mac OS X {os_ver}) "
            f"AppleWebKit/{webkit} (KHTML, like Gecko) "
            f"Chrome/{chrome} Safari/{webkit}"
        )
        fingerprint = {
            "user_agent": user_agent,
            "viewport": [
                viewport[0],
                viewport[1],
            ],  # store as list for JSON compatibility
            "platform": platform,
            "languages": languages,
            "timezone_offset": tz_offset,
        }
        try:
            with open(self.fingerprint_file, "w") as f:
                json.dump(fingerprint, f)
        except Exception:
            pass
        return fingerprint

    def _test_auth(self) -> bool:
        """Lightweight auth test – here we just rely on session status."""
        try:
            status = self.session_manager.get_session_status()
            return bool(status.get("valid"))
        except Exception:
            return False

    def _fresh_login(self, email: str, password: str) -> bool:
        """Attempt an automatic browser-assisted login using Selenium.

        This opens a real browser window to https://es.wallapop.com/auth/signin.
        You complete the login flow manually (captcha/2FA supported). When login
        is detected, session cookies are extracted and persisted, and the access
        token is refreshed via SessionPersistenceManager.

        Returns True when a valid session is available afterwards.
        """
        # Lazy-import heavy deps to avoid cost at import time
        try:
            import importlib

            uc = importlib.import_module("undetected_chromedriver")
            By = importlib.import_module("selenium.webdriver.common.by").By
            WebDriverWait = importlib.import_module(
                "selenium.webdriver.support.ui"
            ).WebDriverWait
            EC = importlib.import_module(
                "selenium.webdriver.support.expected_conditions"
            )
            Options = importlib.import_module(
                "selenium.webdriver.chrome.options"
            ).Options
        except Exception as e:
            print(f"Automatic login unavailable (selenium dependency missing?): {e}")
            return False

        # Ensure session exists and headers are set before we begin
        self._ensure_session()

        # Build a consistent fingerprint for this session
        fp = self._get_session_fingerprint()
        ua = fp.get("user_agent")
        viewport = fp.get("viewport") or [1280, 800]
        width, height = int(viewport[0]), int(viewport[1])

        # Configure the browser
        options = Options()
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        if ua:
            options.add_argument(f"--user-agent={ua}")
        options.add_argument(f"--window-size={width},{height}")

        driver = None
        try:
            print("Starting browser for automatic login...")
            driver = uc.Chrome(options=options)
            driver.get("https://es.wallapop.com/auth/signin")

            # Wait for the page body to load
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except Exception:
                pass

            print("Please complete the Wallapop login in the opened browser.")
            print("The tool will continue automatically once login is detected.")

            # Poll until logged-in state is detected or timeout
            def login_completed() -> bool:
                try:
                    url = driver.current_url
                    # Simple heuristics indicating we are in the app area
                    if any(
                        k in url for k in ("/app/", "/app/catalog", "you", "published")
                    ):
                        return True
                    # Or presence of typical user UI elements
                    els = driver.find_elements(
                        By.CSS_SELECTOR,
                        "[data-testid*='user'], .user-menu, .profile-menu",
                    )
                    return len(els) > 0
                except Exception:
                    return False

            # Up to ~5 minutes, check every 2s
            import time as _time

            max_wait, step, waited = 300, 2, 0
            while waited < max_wait and not login_completed():
                _time.sleep(step)
                waited += step

            if not login_completed():
                print("Login was not detected in time. Closing browser.")
                return False

            # Navigate to a page that triggers federated-session cookie refresh
            try:
                driver.get("https://es.wallapop.com/app/catalog/published")
                _time.sleep(2)
                driver.get("https://es.wallapop.com/api/auth/federated-session")
                _time.sleep(2)
            except Exception:
                pass

            # Extract cookies and persist
            cookies = {}
            try:
                for c in driver.get_cookies():
                    cookies[c.get("name")] = c.get("value")
            except Exception:
                pass

            if not cookies:
                print("Could not read cookies from the browser session.")
                return False

            # Persist and attempt refresh
            try:
                if hasattr(self.session_manager, "save_session"):
                    self.session_manager.save_session(cookies)
            except Exception:
                pass

            ok, _ = self.session_manager.refresh_access_token()
            if not ok:
                print("Failed to refresh access token after automatic login.")
                return False

            # Final quick auth check
            return self._test_auth()

        except Exception as e:
            print(f"Automatic login error: {e}")
            return False
        finally:
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass

    def _manual_cookie_login(self) -> bool:
        """Prompt user to paste cookies manually and persist them via SessionManager.save_session"""
        print("Paste __Secure-next-auth.session-token (end with empty line):")
        session_token = self._get_long_token_input()
        if not session_token:
            return False
        print("Paste __Host-next-auth.csrf-token (end with empty line):")
        csrf_token = self._get_long_token_input()
        if not csrf_token:
            return False
        mpid = input("Enter MPID (optional):").strip()
        device_id = input("Enter device_id (optional):").strip()
        cookies_dict = {
            "__Secure-next-auth.session-token": session_token,
            "__Host-next-auth.csrf-token": csrf_token,
        }
        if mpid:
            cookies_dict["MPID"] = mpid
        if device_id:
            cookies_dict["device_id"] = device_id
        try:
            if hasattr(self.session_manager, "save_session"):
                self.session_manager.save_session(cookies_dict)
        except Exception:
            pass
        if not self.refresh_access_token():
            return False
        return self._test_auth()

    def _get_long_token_input(self):
        import sys

        lines = []
        while True:
            line = sys.stdin.readline()
            if line is None or line == "":
                break
            if line.strip() == "":
                break
            lines.append(line.rstrip("\n"))
        token = "".join(lines)
        final_token = "".join(token.split())
        return final_token

    def login(self, email: str, password: str) -> bool:
        """Legacy login workflow used by tests. Tries session, then fresh, then manual fallback."""
        # Try to reuse existing session
        if self.session_manager.load_session() and self._test_auth():
            self._ensure_session()
            return True

        # Try fresh login (usually patched in tests)
        if self._fresh_login(email, password):
            self._ensure_session()
            return True

        # Manual cookie extraction fallback
        choice = (input("Manual cookie extraction? [Y/n]: ").strip() or "y").lower()
        if choice in ("y", "yes"):
            ok = self._manual_cookie_login()
            if ok:
                self._ensure_session()
            return ok
        return False

    def get_session_status(self) -> Dict[str, Any]:
        """Get current session status and information"""
        try:
            summary = self.session_manager.get_session_status()
        except Exception:
            summary = {"valid": False, "reason": "Unknown"}
        return {
            "valid": bool(summary.get("valid", False)),
            "expires": summary.get("expires"),
            "expires_readable": summary.get("expires_readable"),
            "cookies_count": len(self.session.cookies) if self.session else 0,
            "session_file_exists": self.session_manager.session_file.exists(),
            "source": getattr(self.session_manager, "cookies_file", "session"),
        }

    def get_user_products(self) -> List[Dict[str, Any]]:
        """Fetch all products for the authenticated user"""
        try:
            self._ensure_session()
            # HAR-aligned headers that appear in app calls
            mpid = self.session.cookies.get("MPID", "")
            device_id = self.session.cookies.get("device_id", "")
            extra_headers = {
                "Referer": "https://es.wallapop.com/",
                "Origin": "https://es.wallapop.com",
                "X-AppVersion": "810840",
                "X-DeviceID": device_id or "",
                "X-DeviceOS": "0",
                "DeviceOS": "0",
            }
            if mpid:
                extra_headers["MPID"] = mpid

            # Make authenticated request to get user products
            response = self._make_authenticated_request(
                "GET", f"{self.base_url}/api/v3/user/items", headers=extra_headers
            )

            if response and response.status_code == 200:
                raw = response.json()
                items: List[Dict[str, Any]] = []
                if isinstance(raw, list):
                    items = raw
                elif isinstance(raw, dict):
                    if isinstance(raw.get("data"), list):
                        items = raw.get("data") or []
                    elif isinstance(raw.get("data"), dict) and isinstance(
                        raw["data"].get("products"), list
                    ):
                        items = raw["data"].get("products") or []
                    elif isinstance(raw.get("products"), list):
                        items = raw.get("products") or []

                # Normalize shape for downstream code: id, name, price (float), last_modified
                normalized: List[Dict[str, Any]] = []

                def extract_flag(value: Any) -> bool:
                    if isinstance(value, dict):
                        return bool(value.get("flag"))
                    return bool(value)

                for p in items:
                    pid = p.get("id") or p.get("item_id")
                    title = p.get("title") or p.get("name") or ""
                    price_raw = p.get("price")
                    price: float
                    if isinstance(price_raw, dict) and "amount" in price_raw:
                        price = float(price_raw.get("amount") or 0)
                    else:
                        try:
                            price = (price_raw or 0) / 100.0
                        except Exception:
                            price = 0.0
                    last_mod = p.get("modified_date") or p.get("last_modified")

                    reserved_flag = extract_flag(p.get("reserved"))
                    sold_flag = extract_flag(p.get("sold"))
                    pending_flag = extract_flag(p.get("pending"))
                    blocked_flag = extract_flag(p.get("blocked"))
                    on_hold_flag = extract_flag(p.get("on_hold") or p.get("onhold"))

                    flags = {
                        "reserved": reserved_flag,
                        "sold": sold_flag,
                        "pending": pending_flag,
                        "blocked": blocked_flag,
                        "on_hold": on_hold_flag,
                    }

                    for key, value in p.items():
                        if key in flags:
                            continue
                        if isinstance(value, dict) and "flag" in value:
                            flags[key] = bool(value.get("flag"))

                    normalized.append(
                        {
                            "id": pid,
                            "name": title,
                            "price": price,
                            "last_modified": last_mod,
                            "status": "reserved" if reserved_flag else "available",
                            "reserved": reserved_flag,
                            "flags": flags,
                            # keep original too for any custom needs
                            "_raw": p,
                        }
                    )
                return normalized
            else:
                # Log a short snippet of the body for diagnostics
                body = ""
                if response is not None:
                    try:
                        body = response.text[:300]
                    except Exception:
                        body = ""
                print(
                    f"Failed to fetch products: {response.status_code if response else 'No response'} {body}"
                )
                return []

        except Exception as e:
            print(f"Error fetching user products: {e}")
            return []

    def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Get detailed product information for editing"""
        try:
            mpid = self.session.cookies.get("MPID", "")
            device_id = self.session.cookies.get("device_id", "")
            extra_headers = {
                "Referer": "https://es.wallapop.com/",
                "X-AppVersion": "89340",
                "X-DeviceOS": "0",
            }
            if mpid:
                extra_headers["MPID"] = mpid
            if device_id:
                extra_headers["X-DeviceID"] = device_id

            response = self._make_authenticated_request(
                "GET",
                f"{self.base_url}/api/v3/items/{product_id}/edit?language=es",
                headers=extra_headers,
            )

            if response and response.status_code == 200:
                return response.json()
            else:
                print(
                    f"Failed to get product details: {response.status_code if response else 'No response'}"
                )
                return {}

        except Exception as e:
            print(f"Error getting product details: {e}")
            return {}

    def update_product_price(self, product_id: str, new_price: float) -> bool:
        """Update product price"""
        try:
            self._ensure_session()
            # First get current product details
            current_details = self.get_product_details(product_id)
            if not current_details:
                print("Could not get current product details")
                return False

            # Extract required fields and update price using the correct API payload structure
            data = current_details

            # Extract the proper field values based on actual API response structure
            title = (
                data.get("title", {}).get("original")
                if isinstance(data.get("title"), dict)
                else data.get("title")
            )
            description = (
                data.get("description", {}).get("original")
                if isinstance(data.get("description"), dict)
                else data.get("description")
            )

            # Get category from taxonomy if available - use the most specific one (last in array)
            category_leaf_id = None
            taxonomy = data.get("taxonomy", [])
            if taxonomy and len(taxonomy) > 0:
                category_leaf_id = taxonomy[-1].get("id")

            # Get condition from type_attributes and map to API expected values
            condition = None
            type_attributes = data.get("type_attributes", {})
            if "condition" in type_attributes:
                api_condition = type_attributes["condition"].get("value")
                # Map API response conditions to expected values (see HAR payloads)
                condition_mapping = {
                    "as_good_as_new": "good",
                }
                condition = condition_mapping.get(api_condition, api_condition)

            # Extract location data
            location = data.get("location", {})

            # Extract delivery/shipping info
            shipping = data.get("shipping", {})
            delivery_info = {
                "allowed_by_user": shipping.get("user_allows_shipping"),
                "max_weight_kg": shipping.get("max_weight_kg")
                or shipping.get("max_weight")
                or shipping.get("weight"),
            }

            # Extract any brand info if available
            brand = None
            if "brand" in type_attributes:
                brand = type_attributes["brand"].get("value")

            # Build the correct payload structure as shown in the HAR file
            payload = {
                "attributes": {
                    "title": title,
                    "description": description,
                    "condition": condition,
                },
                "category_leaf_id": category_leaf_id,
                "price": {
                    "cash_amount": round(
                        new_price, 2
                    ),
                    "currency": "EUR",
                    "apply_discount": False,
                },
                "location": {
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "approximated": location.get("approximated", False),
                },
                "delivery": delivery_info,
            }

            # Add brand if available
            if brand:
                payload["attributes"]["brand"] = brand

            # Remove None values from nested structures
            def clean_dict(value):
                if isinstance(value, dict):
                    cleaned = {}
                    for key, nested in value.items():
                        cleaned_value = clean_dict(nested)
                        if cleaned_value in (None, {}, []):
                            continue
                        cleaned[key] = cleaned_value
                    return cleaned
                if isinstance(value, list):
                    cleaned_list = [
                        clean_dict(item) for item in value if item is not None
                    ]
                    return [item for item in cleaned_list if item not in ({}, [])]
                return value

            payload = clean_dict(payload)

            print(f"Updating product {product_id} price to €{new_price}")

            # Make authenticated PUT request to update the product with correct headers
            url = f"{self.base_url}/api/v3/items/{product_id}"

            # Add the specific headers used by the web interface
            extra_headers = {
                "Accept": "application/vnd.upload-v2+json",
                "Content-Type": "application/json",
                "Referer": "https://es.wallapop.com/",
                "Origin": "https://es.wallapop.com",
                "X-AppVersion": "811030",
                "X-DeviceOS": "0",
                "DeviceOS": "0",
            }

            # Add device ID if available from session
            if hasattr(self.session, "cookies"):
                device_id = self.session.cookies.get("device_id", "")
                if device_id:
                    extra_headers["X-DeviceID"] = device_id

            response = self._make_authenticated_request(
                "PUT", url, json=payload, headers=extra_headers
            )

            if response and response.status_code in [200, 204]:
                print(f"✓ Price updated successfully to €{new_price}")
                return True
            else:
                print(
                    f"Update failed: {response.status_code if response else 'No response'}"
                )
                if response and response.text:
                    print(f"Error response: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"Error updating product price: {e}")
            return False

    def refresh_session(self) -> bool:
        """Refresh the session if needed"""
        # Backwards compatibility: delegate to access token refresh
        ok, _ = self.session_manager.refresh_access_token()
        return ok

    # Allow tests to patch this method directly
    def refresh_access_token(self) -> bool:
        ok, _ = self.session_manager.refresh_access_token()
        return ok

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        # Clean up if needed
        pass
