"""Test basic functionality of the SessionManager class."""

import json
import os
import tempfile
from datetime import datetime, timedelta
import pytest

from wallapop_auto_adjust.session_manager import SessionManager


class TestSessionManager:
    """Test cases for SessionManager class."""

    def test_session_manager_creation(self):
        """Test that SessionManager can be instantiated."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            session_file = tmp.name
            
        try:
            session_manager = SessionManager(session_file)
            assert session_manager is not None
            assert session_manager.session_file == session_file
            assert session_manager.session is not None
        finally:
            if os.path.exists(session_file):
                os.unlink(session_file)

    def test_save_session(self):
        """Test that session data can be saved."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            session_file = tmp.name
            
        try:
            session_manager = SessionManager(session_file)
            test_cookies = {"test_cookie": "test_value"}
            test_headers = {"User-Agent": "test-agent"}
            
            session_manager.save_session(test_cookies, test_headers)
            
            # Verify file was created and contains expected data
            assert os.path.exists(session_file)
            with open(session_file, 'r') as f:
                data = json.load(f)
                assert data["cookies"] == test_cookies
                assert data["headers"] == test_headers
                assert "timestamp" in data
        finally:
            if os.path.exists(session_file):
                os.unlink(session_file)

    def test_load_nonexistent_session(self):
        """Test loading a session file that doesn't exist."""
        with tempfile.NamedTemporaryFile(delete=True, suffix='.json') as tmp:
            session_file = tmp.name
            
        # File was deleted, should not exist
        session_manager = SessionManager(session_file)
        result = session_manager.load_session()
        assert result is False

    def test_clear_session(self):
        """Test clearing a session file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            session_file = tmp.name
            
        try:
            session_manager = SessionManager(session_file)
            
            # Create a session file
            test_cookies = {"test_cookie": "test_value"}
            session_manager.save_session(test_cookies)
            assert os.path.exists(session_file)
            
            # Clear the session
            session_manager.clear_session()
            assert not os.path.exists(session_file)
        finally:
            if os.path.exists(session_file):
                os.unlink(session_file)