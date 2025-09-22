#!/usr/bin/env python3
"""
Manual Cookie Guide (file-based) for Wallapop Session Management

This guide uses a root-level cookies.json file that the user edits in their editor.
It validates by obtaining an accessToken and, on success, saves your session under
your home directory: ~/.wallapop-auto-adjust.
"""

# === String Constants ===
CALLBACK_URL = "https%3A%2F%2Fes.wallapop.com%2Fapp%2Fcatalog%2Fpublished"
REQUIRED_COOKIES = [
    '__Secure-next-auth.session-token',
    '__Host-next-auth.csrf-token',
]
OPTIONAL_COOKIES = [
    'device_id',
]
ROOT_COOKIE_KEYS = [
    "__Secure-next-auth.session-token",
    "__Host-next-auth.csrf-token",
    "__Secure-next-auth.callback-url",
    "device_id",
]
CHROME_COOKIE_PATH = "Chrome → F12 → Application → Cookies → https://es.wallapop.com"
TEMPLATE_INSTRUCTIONS = (
    "Open and log into a Wallapop session in Chrome"
    "→ Open Chrome DevTools (F12) → Go to Application → Cookies → https://es.wallapop.com.\n"
    "Right-click the Value cell → Copy value for each field below, then paste below.\n"
    "Required: __Secure-next-auth.session-token, __Host-next-auth.csrf-token.\n"
    "Optional: device_id."
)

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any


class CookieExtractionGuide:
    """File-based guide for extracting fresh session cookies"""

    # Use the current callback URL as a constant; we pre-fill this in the template

    def __init__(self):
        self.required_cookies = REQUIRED_COOKIES
        self.optional_cookies = OPTIONAL_COOKIES
        # Resolve repo root for the editable template file
        repo_root = Path(__file__).resolve().parents[2]
        # Session home under user directory (same as SessionPersistenceManager)
        base_dir = Path.home() / '.wallapop-auto-adjust'
        base_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = base_dir / 'session_data.json'
        self.cookies_file = base_dir / 'cookies.json'
        self.root_cookies_path = repo_root / 'cookies.json'

    def show_welcome(self):
        print("=" * 60)
        print("🔑 WALLAPOP MANUAL COOKIE SETUP")
        print("=" * 60)
        print()
        print("I will now guide you through copying Wallapop cookies from an active Wallapop" \
        " session in your browser so that they can be used here.")
        print()
        print("📋 What you'll need:")
        print("  • An active Wallapop session in your browser")
        print("  • Chrome Browser")
        print("  • 3 minutes of your time")
        print()
        print("🎯 What you'll get:")
        print("  • 30 days of automatic authentication")
        print()

    def check_existing_session(self):
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text())
                expires_str = data.get('expires')
                if expires_str:
                    expires = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                    if expires > datetime.now():
                        days_left = (expires - datetime.now()).days
                        print(f"🟢 EXISTING SESSION FOUND")
                        print(f"   Valid for {days_left} more days")
                        print(f"   Expires: {expires.strftime('%Y-%m-%d %H:%M:%S')}")
                        print()
                        choice = input("Do you want to use the existing session? (Y/n): ").strip().lower()
                        if choice in ('', 'y', 'yes'):
                            print("✅ Using existing session")
                            return True
                        else:
                            print("🔄 Will extract fresh cookies")
                            return False
                    else:
                        print("⚠️  Existing session has expired")
                        return False
            except Exception:
                print("⚠️  Existing session file is corrupted")
                return False
        return False

    def _template_content(self) -> Dict[str, Any]:
        return {
            "instructions": TEMPLATE_INSTRUCTIONS,
            "__Secure-next-auth.session-token": "",
            "__Host-next-auth.csrf-token": "",
            "__Secure-next-auth.callback-url": CALLBACK_URL,
            "device_id": ""
        }

    def ensure_root_template(self) -> None:
        if not self.root_cookies_path.exists():
            try:
                # Keep unicode arrows and symbols readable in file
                self.root_cookies_path.write_text(json.dumps(self._template_content(), indent=2, ensure_ascii=False))
                print(f"📝 Created template at: {self.root_cookies_path}")
            except Exception as e:
                print(f"❌ Failed to create template: {e}")
        else:
            # Ensure callback-url is up-to-date
            try:
                data = json.loads(self.root_cookies_path.read_text())
                if not data.get("__Secure-next-auth.callback-url"):
                    data["__Secure-next-auth.callback-url"] = CALLBACK_URL
                    self.root_cookies_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            except Exception:
                pass

    def show_file_instructions(self):
        print("🌐 MANUAL COOKIE FILE INSTRUCTIONS")
        print("-" * 36)
        print()
        print(f"Edit this file: {self.root_cookies_path}")
        print(f"Fill these fields exactly as in {CHROME_COOKIE_PATH}:")
        for cookie in self.required_cookies:
            print(f"  • {cookie} (required)")
        for cookie in self.optional_cookies:
            print(f"  • {cookie} (optional)")
        input("Press Enter when you have edited and saved cookies.json...")

    def read_root_cookies(self) -> Dict[str, str]:
        try:
            data: Dict[str, Any] = json.loads(self.root_cookies_path.read_text())
        except Exception as e:
            print(f"❌ Failed to read {self.root_cookies_path}: {e}")
            return {}
        cookies: Dict[str, str] = {}
        for k in ROOT_COOKIE_KEYS:
            v = data.get(k)
            if isinstance(v, str):
                cookies[k] = v.strip()
        # Ensure callback present
        cookies.setdefault("__Secure-next-auth.callback-url", CALLBACK_URL)
        return cookies

    def validate_cookies(self, cookies: Dict[str, str]):
        print("\n🔍 VALIDATING COOKIES")
        missing = [c for c in self.required_cookies if not cookies.get(c)]
        if missing:
            print("❌ Missing required cookies:")
            for c in missing:
                print(f"   • {c}")
            return False
        if len(cookies.get('__Secure-next-auth.session-token', '')) < 1000:
            print("⚠️  Session token seems short (<1000 chars)")
        if len(cookies.get('__Host-next-auth.csrf-token', '')) < 50:
            print("⚠️  CSRF token seems short (<50 chars)")
        # Callback URL is auto-set; confirm presence
        print("✅ Cookie validation passed")
        return True

    def save_session_data(self, cookies: Dict[str, str]):
        print("\n💾 SAVING SESSION DATA")
        expires = datetime.now() + timedelta(days=30)
        # Ensure callback-url is set
        cookies = dict(cookies)
        cookies.setdefault('__Secure-next-auth.callback-url', CALLBACK_URL)

        session_data = {
            'cookies': cookies,
            'created': datetime.now().isoformat(),
            'expires': expires.isoformat(),
            'version': '1.0'
        }
        try:
            # Save session file
            self.session_file.write_text(json.dumps(session_data, indent=2))
            print(f"✅ Session saved to {self.session_file}")
            # Also write cookies.json for SessionPersistenceManager fallback
            self.cookies_file.write_text(json.dumps(cookies, indent=2))
            print(f"✅ Cookies saved to {self.cookies_file}")
            print(f"✅ Valid until: {expires.strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        except Exception as e:
            print(f"❌ Failed to save session: {e}")
            return False

    def test_session(self, cookies: Dict[str, str]):
        print("\n🧪 TESTING SESSION")
        # Prefer using the package SessionPersistenceManager for a robust validation
        try:
            from .session_persistence import SessionPersistenceManager
        except Exception:
            # Fallback to runtime import path
            try:
                from wallapop_auto_adjust.session_persistence import SessionPersistenceManager
            except Exception as e:
                print(f"❌ Could not import SessionPersistenceManager: {e}")
                return False

        try:
            spm = SessionPersistenceManager()
            # Load from the provided cookies dict (no persistence yet)
            if not spm.load_from_cookies_dict(cookies):
                print("❌ Failed to initialize session from provided cookies")
                return False
            ok, token_or_err = spm.refresh_access_token()
            if ok:
                print("✅ Session validated: accessToken acquired")
                return True
            else:
                print(f"❌ Session validation failed: {token_or_err}")
                return False
        except Exception as e:
            print(f"❌ Unexpected error during validation: {e}")
            return False

    def show_completion(self):
        print("\n" + "=" * 60)
        print("🎉 COOKIE EXTRACTION COMPLETE!")
        print("=" * 60)

    def run(self):
        self.show_welcome()
    # If a valid saved session exists and works, just use it
        try:
            from .session_persistence import SessionPersistenceManager
            spm = SessionPersistenceManager()
            if spm.load_session():
                ok, _ = spm.refresh_access_token()
                if ok:
                    print("🟢 Using existing saved session")
                    return True
                else:
                    print("⚠️ Existing saved session did not validate; need fresh cookies")
        except Exception:
            pass

        # Ensure the root cookies.json template exists
        self.ensure_root_template()
        self.show_file_instructions()

        # Read and validate from root file
        cookies = self.read_root_cookies()
        if not self.validate_cookies(cookies):
            return False
        # Test without persisting
        if not self.test_session(cookies):
            print("❌ Validation failed. Please re-open and update the root cookies.json and run again.")
            return False

    # Persist to ~/.wallapop-auto-adjust for future runs
        if not self.save_session_data(cookies):
            return False
        self.show_completion()
        return True


def main():
    guide = CookieExtractionGuide()
    ok = guide.run()
    print("Cookie extraction completed successfully!" if ok else "Cookie extraction was not completed.")


if __name__ == "__main__":
    main()
