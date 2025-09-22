import json
from datetime import datetime, timedelta
from pathlib import Path

import types

from wallapop_auto_adjust.cookie_extraction_guide import CookieExtractionGuide


class StubSPM:
    def __init__(self):
        self.loaded = False
        self.refreshed = False

    def load_from_cookies_dict(self, cookies):
        # Simulate successful in-memory load
        self.loaded = True
        return True

    def refresh_access_token(self):
        # Simulate obtaining an accessToken
        self.refreshed = True
        return True, 'GUIDE_TOKEN'


def test_cookie_guide_validation_and_persist(tmp_path, monkeypatch):
    # Create guide and redirect its paths into tmp
    guide = CookieExtractionGuide()
    guide_root = tmp_path
    guide.root_cookies_path = guide_root / 'cookies.json'
    guide.session_file = guide_root / '.session' / 'session_data.json'
    guide.cookies_file = guide_root / '.session' / 'cookies.json'
    guide.cookies_file.parent.mkdir(parents=True, exist_ok=True)

    # Prepare a root cookies file with required fields
    cookies_payload = {
        "__Secure-next-auth.session-token": "S" * 1200,
        "__Host-next-auth.csrf-token": "C" * 64,
        # callback-url will be auto-filled if missing
    }
    guide.root_cookies_path.write_text(json.dumps(cookies_payload))

    # Patch the SessionPersistenceManager used within the guide to our stub
    # Patch the real class so imports inside guide refer to our stub
    import wallapop_auto_adjust.session_persistence as spm_module
    monkeypatch.setattr(spm_module, 'SessionPersistenceManager', StubSPM)

    # Read, validate and test the session without persistence
    cookies = guide.read_root_cookies()
    assert guide.validate_cookies(cookies) is True
    assert guide.test_session(cookies) is True

    # Now save and ensure files are written with a ~30-day expiry
    assert guide.save_session_data(cookies) is True
    assert guide.session_file.exists()
    data = json.loads(guide.session_file.read_text())
    assert 'cookies' in data and '__Secure-next-auth.session-token' in data['cookies']
    # Check expiration roughly 29-31 days ahead
    expires = datetime.fromisoformat(data['expires'])
    delta = expires - datetime.now()
    assert timedelta(days=29) < delta < timedelta(days=31)
    # cookies.json mirror also written
    assert guide.cookies_file.exists()
