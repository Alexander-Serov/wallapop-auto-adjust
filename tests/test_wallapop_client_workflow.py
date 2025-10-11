import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wallapop_auto_adjust.wallapop_client import WallapopClient


class TestWallapopClientLoginWorkflow(unittest.TestCase):
    """Test the multi-step login workflow and fallback mechanisms"""

    def setUp(self):
        """Set up test fixtures"""
        with patch("wallapop_auto_adjust.wallapop_client.SessionManager"):
            self.client = WallapopClient()

    def test_login_workflow_sequence(self):
        """Test that login method follows the correct sequence"""
        with (
            patch.object(
                self.client.session_manager, "load_session", return_value=False
            ),
            patch.object(self.client, "_fresh_login", return_value=False) as mock_fresh,
            patch.object(
                self.client, "_manual_cookie_login", return_value=True
            ) as mock_manual,
            patch("builtins.input", return_value="y"),
        ):

            result = self.client.login("test@email.com", "password")

            # Should try fresh login first
            mock_fresh.assert_called_once_with("test@email.com", "password")
            # Should fall back to manual when fresh fails
            mock_manual.assert_called_once()
            # Should return True when manual succeeds
            self.assertTrue(result)

    def test_login_uses_existing_session_when_valid(self):
        """Test that existing valid session is used"""
        with (
            patch.object(
                self.client.session_manager, "load_session", return_value=True
            ),
            patch.object(self.client, "_test_auth", return_value=True),
            patch.object(self.client, "_fresh_login") as mock_fresh,
        ):

            result = self.client.login("test@email.com", "password")

            # Should not try fresh login when existing session is valid
            mock_fresh.assert_not_called()
            self.assertTrue(result)

    def test_login_tries_fresh_when_session_expired(self):
        """Test that fresh login is attempted when session expires"""
        with (
            patch.object(
                self.client.session_manager, "load_session", return_value=True
            ),
            patch.object(self.client, "_test_auth", return_value=False),
            patch.object(self.client, "_fresh_login", return_value=True) as mock_fresh,
        ):

            result = self.client.login("test@email.com", "password")

            # Should try fresh login when session is expired
            mock_fresh.assert_called_once_with("test@email.com", "password")
            self.assertTrue(result)

    def test_manual_fallback_defaults_to_yes(self):
        """Test that manual cookie extraction defaults to 'y' when user presses Enter"""
        with (
            patch.object(
                self.client.session_manager, "load_session", return_value=False
            ),
            patch.object(self.client, "_fresh_login", return_value=False),
            patch.object(
                self.client, "_manual_cookie_login", return_value=True
            ) as mock_manual,
            patch("builtins.input", return_value=""),
        ):  # Empty string (Enter key)

            result = self.client.login("test@email.com", "password")

            # Should call manual login when user presses Enter (defaults to yes)
            mock_manual.assert_called_once()
            self.assertTrue(result)

    def test_manual_fallback_respects_no(self):
        """Test that manual cookie extraction is skipped when user says no"""
        with (
            patch.object(
                self.client.session_manager, "load_session", return_value=False
            ),
            patch.object(self.client, "_fresh_login", return_value=False),
            patch.object(self.client, "_manual_cookie_login") as mock_manual,
            patch("builtins.input", return_value="n"),
        ):

            result = self.client.login("test@email.com", "password")

            # Should not call manual login when user says no
            mock_manual.assert_not_called()
            self.assertFalse(result)

    def test_session_directory_creation(self):
        """Test that session directory is created during initialization"""
        with (
            patch("wallapop_auto_adjust.wallapop_client.SessionManager"),
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):

            WallapopClient()

            # Should create .tmp directory
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("wallapop_auto_adjust.wallapop_client.random.choice")
    def test_fingerprint_randomization(self, mock_random_choice):
        """Test that browser fingerprint uses randomized values"""
        mock_random_choice.side_effect = [
            "120.0.0.0",  # Chrome version
            "11_7_10",  # OS version
            "537.36",  # WebKit version
            (1920, 1080),  # Viewport
            "MacIntel",  # Platform
            ["en-US", "en"],  # Languages
            -300,  # Timezone offset
        ]

        with patch("wallapop_auto_adjust.wallapop_client.SessionManager"):
            client = WallapopClient()
            fingerprint = client._get_session_fingerprint()

            # Should use randomized values from constants
            self.assertIn("120.0.0.0", fingerprint["user_agent"])
            self.assertEqual(
                fingerprint["viewport"], [1920, 1080]
            )  # JSON stores as list
            self.assertEqual(fingerprint["platform"], "MacIntel")
            self.assertEqual(fingerprint["languages"], ["en-US", "en"])
            self.assertEqual(fingerprint["timezone_offset"], -300)

    def test_fingerprint_persistence(self):
        """Test that fingerprint is saved and reused within session"""
        with patch("wallapop_auto_adjust.wallapop_client.SessionManager"):
            client = WallapopClient()

            # Mock file operations
            mock_file_content = {
                "user_agent": "test-user-agent",
                "viewport": [1920, 1080],  # JSON stores as list, not tuple
                "platform": "MacIntel",
                "languages": ["en-US", "en"],
                "timezone_offset": -300,
            }

            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("builtins.open", mock_open_json(mock_file_content)),
            ):

                fingerprint = client._get_session_fingerprint()

                # Should reuse existing fingerprint
                self.assertEqual(fingerprint["user_agent"], "test-user-agent")
                self.assertEqual(
                    fingerprint["viewport"], [1920, 1080]
                )  # JSON returns list

    def test_manual_cookie_extraction_validation(self):
        """Test that manual cookie extraction validates required fields"""
        with patch("wallapop_auto_adjust.wallapop_client.SessionManager"):
            client = WallapopClient()

            # Test with empty session token
            with patch(
                "sys.stdin.readline", side_effect=["", "\n"]
            ):  # Empty token, then empty line to end
                result = client._manual_cookie_login()
                self.assertFalse(result)

            # Test with valid tokens
            with (
                patch(
                    "sys.stdin.readline",
                    side_effect=[
                        "test-session-token\n",
                        "\n",  # Session token + end marker
                        "test-csrf-token\n",
                        "\n",  # CSRF token + end marker
                        "test-mpid\n",  # MPID
                        "test-device-id\n",  # Device ID
                    ],
                ),
                patch.object(client, "refresh_access_token", return_value=True),
                patch.object(client, "_test_auth", return_value=True),
                patch.object(client.session_manager, "save_session"),
            ):

                result = client._manual_cookie_login()
                self.assertTrue(result)

    def test_get_user_products_includes_reserved_flags(self):
        """Reserved products should be surfaced in normalized payload"""
        self.client._ensure_session = MagicMock()
        self.client.session = MagicMock()
        self.client.session.cookies = {"MPID": "", "device_id": ""}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "pres",
                "title": "Reserved Item",
                "price": {"amount": 12.5, "currency": "EUR"},
                "modified_date": 1234,
                "reserved": {"flag": True},
            }
        ]

        with patch.object(self.client, "_make_authenticated_request", return_value=mock_response):
            products = self.client.get_user_products()

        self.assertEqual(len(products), 1)
        product = products[0]
        self.assertTrue(product["reserved"])
        self.assertEqual(product["status"], "reserved")
        self.assertTrue(product["flags"]["reserved"])


def mock_open_json(data):
    """Helper to mock open() for JSON files"""
    import json
    from unittest.mock import mock_open

    return mock_open(read_data=json.dumps(data))


if __name__ == "__main__":
    unittest.main()
