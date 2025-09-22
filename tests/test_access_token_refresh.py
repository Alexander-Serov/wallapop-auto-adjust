import json
from typing import Callable, Dict, Optional

from requests.cookies import RequestsCookieJar

from wallapop_auto_adjust.session_persistence import SessionPersistenceManager


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        data: Optional[dict] = None,
        set_cookie: Optional[str] = None,
    ):
        self.status_code = status_code
        self._data = data
        self.headers: Dict[str, str] = {}
        self.cookies = RequestsCookieJar()
        if data is None:
            self.text = ""
        else:
            self.text = json.dumps(data)
        if set_cookie:
            self.headers["Set-Cookie"] = set_cookie
            # Also reflect into response cookie jar for convenience
            try:
                # Expect format like 'accessToken=VALUE; Path=/; Domain=.wallapop.com'
                if set_cookie.startswith("accessToken="):
                    value = set_cookie.split("accessToken=", 1)[1].split(";", 1)[0]
                    self.cookies.set(
                        "accessToken", value, domain=".wallapop.com", path="/"
                    )
            except Exception:
                pass

    def json(self):
        return self._data if self._data is not None else {}


class FakeSession:
    def __init__(self, responder: Callable[[str, Dict], FakeResponse]):
        self._responder = responder
        self.cookies = RequestsCookieJar()
        self.headers: Dict[str, str] = {}
        self.calls = []  # list of (method, url, kwargs)

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self._responder(url, kwargs)

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self._responder(url, kwargs)

    def request(self, method: str, url: str, **kwargs):
        if method.upper() == "GET":
            return self.get(url, **kwargs)
        if method.upper() == "POST":
            return self.post(url, **kwargs)
        raise NotImplementedError


def seed_required_cookies(jar: RequestsCookieJar):
    jar.set(
        "__Secure-next-auth.session-token",
        "S" * 1200,
        domain="es.wallapop.com",
        path="/",
        secure=True,
    )
    jar.set(
        "__Host-next-auth.csrf-token",
        "C" * 64,
        domain="es.wallapop.com",
        path="/",
        secure=True,
    )
    jar.set(
        "__Secure-next-auth.callback-url",
        "https%3A%2F%2Fes.wallapop.com%2Fapp%2Fchat",
        domain="es.wallapop.com",
        path="/",
        secure=True,
    )


def test_refresh_token_from_json_token(monkeypatch):
    def responder(url: str, kwargs: Dict):
        if url.endswith("/api/auth/federated-session"):
            return FakeResponse(200, data={"token": "JSON_TOKEN"})
        return FakeResponse(200, data={})

    spm = SessionPersistenceManager()
    spm._http2_available = False  # keep deterministic
    spm.session = FakeSession(responder)
    seed_required_cookies(spm.session.cookies)

    ok, token = spm.refresh_access_token()
    assert ok is True
    assert token == "JSON_TOKEN"
    # accessToken should be set in the cookie jar as well
    assert spm.session.cookies.get("accessToken") == "JSON_TOKEN"
    # federated-session should have been called at least once
    assert any("/api/auth/federated-session" in c[1] for c in spm.session.calls)


def test_refresh_token_from_set_cookie_header(monkeypatch):
    def responder(url: str, kwargs: Dict):
        if url.endswith("/api/auth/federated-session"):
            return FakeResponse(
                200,
                data={},
                set_cookie="accessToken=COOKIE_TKN; Path=/; Domain=.wallapop.com",
            )
        return FakeResponse(200, data={})

    spm = SessionPersistenceManager()
    spm._http2_available = False
    spm.session = FakeSession(responder)
    seed_required_cookies(spm.session.cookies)

    ok, token = spm.refresh_access_token()
    assert ok is True
    assert token == "COOKIE_TKN"
    assert spm.session.cookies.get("accessToken") == "COOKIE_TKN"


def test_query_param_fallback_uses_session_token(monkeypatch):
    calls = {"first": True}

    def responder(url: str, kwargs: Dict):
        if url.endswith("/api/auth/federated-session"):
            params = kwargs.get("params") or {}
            if "token" in params:
                # return success on query param fallback
                return FakeResponse(200, data={"accessToken": "QUERY_TOKEN"})
            # first call returns empty JSON
            return FakeResponse(200, data={})
        return FakeResponse(200, data={})

    spm = SessionPersistenceManager()
    spm._http2_available = False
    spm.session = FakeSession(responder)
    seed_required_cookies(spm.session.cookies)

    ok, token = spm.refresh_access_token()
    assert ok is True
    assert token == "QUERY_TOKEN"
    # Ensure a call with ?token was made
    assert any(
        "/api/auth/federated-session" in url
        and ("params" in kw and "token" in (kw.get("params") or {}))
        for _, url, kw in spm.session.calls
    )


def test_nudge_users_me_sets_cookie(monkeypatch):
    def responder(url: str, kwargs: Dict):
        if url.endswith("/api/auth/federated-session"):
            # Always empty, force fallback path
            return FakeResponse(200, data={})
        if "/api/v3/users/me" in url:
            # Simulate backend setting accessToken cookie when calling users/me
            return FakeResponse(
                200,
                data={},
                set_cookie="accessToken=NUDGE_TKN; Path=/; Domain=.wallapop.com",
            )
        return FakeResponse(200, data={})

    spm = SessionPersistenceManager()
    spm._http2_available = False
    spm.session = FakeSession(responder)
    seed_required_cookies(spm.session.cookies)

    ok, token = spm.refresh_access_token()
    assert ok is True
    assert token == "NUDGE_TKN"


def test_warmup_calls_precede_federated_session():
    state = {"fed_calls": 0}

    def responder(url: str, kwargs: Dict):
        if url.endswith("/api/auth/federated-session"):
            state["fed_calls"] += 1
            if state["fed_calls"] == 1:
                # First time returns empty JSON
                return FakeResponse(200, data={})
            # Second time returns a token
            return FakeResponse(200, data={"token": "SEQUENCE_TOKEN"})
        # All other endpoints 200 with empty JSON
        return FakeResponse(200, data={})

    spm = SessionPersistenceManager()
    spm._http2_available = False
    spm.session = FakeSession(responder)
    seed_required_cookies(spm.session.cookies)

    ok, token = spm.refresh_access_token()
    assert ok is True
    assert token == "SEQUENCE_TOKEN"

    # Verify that app/chat and api/auth/session were called before the first federated-session call
    first_fed_index = next(
        i
        for i, (_, url, _) in enumerate(spm.session.calls)
        if url.endswith("/api/auth/federated-session")
    )
    calls_before = [url for _, url, _ in spm.session.calls[:first_fed_index]]
    assert any(url.endswith("/app/chat") for url in calls_before)
    assert any(url.endswith("/api/auth/session") for url in calls_before)
    # Verify first federated-session call includes cache-busting and ETag header
    _, fed_url, fed_kw = spm.session.calls[first_fed_index]
    params = fed_kw.get("params") or {}
    headers = fed_kw.get("headers") or {}
    assert "_" in params
    assert "if-none-match" in {k.lower(): v for k, v in headers.items()}


def test_load_from_cookies_dict_normalizes_cookie_names():
    # Provide single-underscore variants with spaces/quotes
    input_cookies = {
        "_Secure-next-auth.session-token": "  'S' * 1000  ",
        "_Host-next-auth.csrf-token": '  "C" * 64  ',
    }
    # Replace with realistic long strings after stripping quotes in implementation
    input_cookies["_Secure-next-auth.session-token"] = " '" + ("S" * 1000) + "' "
    input_cookies["_Host-next-auth.csrf-token"] = ' "' + ("C" * 64) + '" '

    spm = SessionPersistenceManager()
    ok = spm.load_from_cookies_dict(input_cookies)
    assert ok is True
    # Canonical cookies must be present in jar
    assert spm.session.cookies.get("__Secure-next-auth.session-token") is not None
    assert spm.session.cookies.get("__Host-next-auth.csrf-token") is not None
    # Aliases should not be set in the jar (they are only for lookups)
    assert spm.session.cookies.get("_Secure-next-auth.session-token") is None
    assert spm.session.cookies.get("_Host-next-auth.csrf-token") is None


def test_make_authenticated_request_sets_bearer_header():
    def responder(url: str, kwargs: Dict):
        if url.endswith("/api/auth/federated-session"):
            return FakeResponse(200, data={"token": "BEARER_TOKEN"})
        # Return 200 OK to the target API call
        return FakeResponse(200, data={"ok": True})

    spm = SessionPersistenceManager()
    spm._http2_available = False
    spm.session = FakeSession(responder)
    seed_required_cookies(spm.session.cookies)

    resp = spm.make_authenticated_request(
        "GET", "https://api.wallapop.com/api/v3/users/me/"
    )
    assert resp.status_code == 200
    # Find the API call and inspect headers
    api_calls = [
        (m, url, kw)
        for (m, url, kw) in spm.session.calls
        if url.startswith("https://api.wallapop.com/api/v3/users/me/")
    ]
    assert api_calls, "Expected an API call to users/me"
    last_call = api_calls[-1]
    headers = last_call[2].get("headers") or {}
    assert headers.get("Authorization") == "Bearer BEARER_TOKEN"


def test_make_authenticated_request_retries_on_401():
    state = {"first_api_call": True}

    def responder(url: str, kwargs: Dict):
        if url.endswith("/api/auth/federated-session"):
            return FakeResponse(200, data={"token": "RETRY_TOKEN"})
        if url.startswith("https://api.wallapop.com/api/v3/users/me/"):
            if state["first_api_call"]:
                state["first_api_call"] = False
                # Simulate expired token
                resp = FakeResponse(401, data={})
                return resp
            return FakeResponse(200, data={"ok": True})
        return FakeResponse(200, data={})

    spm = SessionPersistenceManager()
    spm._http2_available = False
    spm.session = FakeSession(responder)
    seed_required_cookies(spm.session.cookies)

    resp = spm.make_authenticated_request(
        "GET", "https://api.wallapop.com/api/v3/users/me/"
    )
    assert resp.status_code == 200
    # Ensure there were at least two calls to users/me (initial + retry)
    user_calls = [
        c
        for c in spm.session.calls
        if c[1].startswith("https://api.wallapop.com/api/v3/users/me/")
    ]
    assert len(user_calls) >= 2
