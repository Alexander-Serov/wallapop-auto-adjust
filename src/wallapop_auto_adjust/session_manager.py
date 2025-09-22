import json
import os
from datetime import datetime, timedelta
import requests


class SessionManager:
    def __init__(self, session_file="wallapop_session.json"):
        self.session_file = session_file
        self.session = requests.Session()

    def save_session(self, cookies_dict, headers_dict=None):
        """Save session cookies and headers to file"""
        session_data = {
            "cookies": cookies_dict,
            "headers": headers_dict or {},
            "timestamp": datetime.now().isoformat(),
        }

        with open(self.session_file, "w") as f:
            json.dump(session_data, f, indent=2)

    def load_session(self):
        """Load session from file if it exists and is recent"""
        if not os.path.exists(self.session_file):
            return False

        try:
            with open(self.session_file, "r") as f:
                session_data = json.load(f)

            # Check if session is less than 24 hours old
            saved_time = datetime.fromisoformat(session_data["timestamp"])
            if datetime.now() - saved_time > timedelta(hours=24):
                return False

            # Restore cookies
            for name, value in session_data["cookies"].items():
                self.session.cookies.set(name, value)

            # Restore headers if any
            if session_data.get("headers"):
                self.session.headers.update(session_data["headers"])

            return True

        except Exception as e:
            print(f"Failed to load session: {e}")
            return False

    def test_session(self, test_url):
        """Test if current session is valid"""
        try:
            response = self.session.get(test_url)
            return response.status_code == 200
        except:
            return False

    def clear_session(self):
        """Clear saved session file"""
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
