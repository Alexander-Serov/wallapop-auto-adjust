#!/usr/bin/env python3
"""
Advanced Session Manager for Wallapop Auto-Adjust

Handles 30-day session persistence with automatic 5-minute token refresh
"""

import json
import os
import logging
import requests
import contextlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

class SessionPersistenceManager:
    """Manages persistent sessions with automatic token refresh"""
    
    def __init__(self, session_file: str = "session_data.json", cookies_file: str = "cookies.json"):
        # Place all session artifacts under user home by default (no env override)
        base_dir = Path.home() / '.wallapop-auto-adjust'
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.session_file = (base_dir / session_file)
        self.cookies_file = (base_dir / cookies_file)
        self.logger = logging.getLogger(__name__)
        # Enable verbose debug if requested
        if os.getenv('WALLAPOP_DEBUG'):
            try:
                logging.getLogger().setLevel(logging.DEBUG)
                self.logger.setLevel(logging.DEBUG)
            except Exception:
                pass
        self.current_token = None
        self.token_expires_at = None
        self.session = None
        self.session_data = None
        # One-time migration from legacy repo-local .session directory
        try:
            legacy_dir = Path(__file__).resolve().parents[2] / '.session'
            if legacy_dir.exists():
                for fname in (session_file, cookies_file):
                    src = legacy_dir / fname
                    dst = base_dir / fname
                    if src.exists() and not dst.exists():
                        import shutil
                        shutil.copy2(src, dst)
                        self.logger.info(f"Migrated legacy {src} to {dst}")
                        # Also print to stdout so users notice the one-time migration
                        try:
                            print(f"Migrated legacy {src} to {dst}")
                        except Exception:
                            pass
        except Exception:
            # Best-effort migration; ignore errors
            pass
        
        # Token refresh settings
        self.token_refresh_url = "https://es.wallapop.com/api/auth/federated-session"
        self.token_lifetime_minutes = 5
        self.refresh_buffer_seconds = 30  # Refresh 30 seconds before expiry
        # Optional: enable HTTP/2 fallback via httpx if installed
        self._http2_available = False
        with contextlib.suppress(Exception):
            import httpx  # type: ignore
            self._http2_available = True
    
    def load_session(self) -> bool:
        """Load session from persistent storage or cookies.json fallback"""
        try:
            if self.session_file.exists():
                with open(self.session_file, 'r') as f:
                    self.session_data = json.load(f)
                # Check if session is expired
                if not self._is_session_valid():
                    self.logger.warning("Stored session has expired")
                    self.session_data = None
            
            # Fallback: load from cookies.json if no valid session_data
            # If cookies.json exists, prioritize its cookies (fresh from browser) even if a session file exists
            if self.cookies_file.exists():
                try:
                    self.logger.info(f"Loading cookies from {self.cookies_file} (priority over session_data if present)")
                    with open(self.cookies_file, 'r') as f:
                        raw = json.load(f)
                    cookies_from_file: Dict[str, str] = {
                        k: v for k, v in raw.items()
                        if isinstance(v, str) and k not in {"instructions", "notes"}
                    }
                    if not self.session_data:
                        now = datetime.now()
                        expires = now + timedelta(days=30)
                        self.session_data = {
                            'cookies': cookies_from_file,
                            'created': now.isoformat(),
                            'expires': expires.isoformat(),
                            'source': 'cookies.json',
                        }
                    else:
                        # Merge/override cookies
                        merged = dict(self.session_data.get('cookies', {}))
                        merged.update(cookies_from_file)
                        self.session_data['cookies'] = merged
                        self.session_data['source'] = 'cookies.json+session'
                    self.logger.info("Cookies from cookies.json are now active")
                except Exception as e:
                    self.logger.error(f"Failed to load cookies.json: {e}")
                    # continue with existing session_data if any
            
            if not self.session_data:
                self.logger.warning(f"No session data available (no {self.session_file} or valid cookies.json)")
                return False
            
            # Create requests session with cookies
            self.session = requests.Session()
            cookies = self.session_data.get('cookies', {})

            # Sanitize cookie values: trim whitespace/newlines and strip surrounding quotes
            sanitized: Dict[str, str] = {}
            for k, v in cookies.items():
                if isinstance(v, str):
                    vv = v.strip()
                    # Remove accidental surrounding quotes
                    if (vv.startswith('"') and vv.endswith('"')) or (vv.startswith("'") and vv.endswith("'")):
                        vv = vv[1:-1]
                    sanitized[k] = vv
                else:
                    sanitized[k] = v
            cookies = sanitized

            # Normalize NextAuth cookie names: browsers use double underscores for __Host-/__Secure-
            # Accept either variant in cookies.json and set both to maximize compatibility
            normalized: Dict[str, str] = dict(cookies)
            mapping_pairs = [
                ("_Secure-next-auth.session-token", "__Secure-next-auth.session-token"),
                ("_Host-next-auth.csrf-token", "__Host-next-auth.csrf-token"),
                ("_Secure-next-auth.callback-url", "__Secure-next-auth.callback-url"),
            ]
            for single, double in mapping_pairs:
                if single in cookies and double not in normalized:
                    normalized[double] = cookies[single]
                if double in cookies and single not in normalized:
                    # Also expose a single-underscore alias for downstream lookups
                    normalized[single] = cookies[double]

            from requests.cookies import create_cookie
            # Only set canonical cookie names to avoid duplicates; prefer double-underscore
            def should_set_cookie(name: str) -> bool:
                if name.startswith('_Secure-next-auth.') or name.startswith('_Host-next-auth.'):
                    return False  # aliases for internal lookups only
                return True

            for name, value in normalized.items():
                if not should_set_cookie(name):
                    continue
                # Ensure path is root so requests includes cookie broadly
                try:
                    cookies_to_set = []
                    # Canonical domains per cookie (based on browser behavior):
                    # - __Host-next-auth.csrf-token → es.wallapop.com (host-only)
                    # - __Secure-next-auth.callback-url → es.wallapop.com (host-only)
                    # - __Secure-next-auth.session-token → .wallapop.com
                    # - device_id, accessToken (and most others) → .wallapop.com
                    if name == '__Host-next-auth.csrf-token' or name == '__Secure-next-auth.callback-url':
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='es.wallapop.com', path='/', secure=True))
                    elif name == '__Secure-next-auth.session-token' or name == 'device_id' or name == 'accessToken':
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='.wallapop.com', path='/', secure=True))
                    elif name.startswith('__Host-'):
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='es.wallapop.com', path='/', secure=True))
                    else:
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='.wallapop.com', path='/', secure=True))

                    # Remove any existing cookie entries with the same name across domains/paths (best effort)
                    try:
                        for c in list(self.session.cookies):
                            if c.name == name:
                                with contextlib.suppress(Exception):
                                    self.session.cookies.clear(domain=c.domain, path=c.path, name=c.name)
                    except Exception:
                        pass
                    for ck in cookies_to_set:
                        self.session.cookies.set_cookie(ck)
                except Exception:
                    # Fallback to simple set with canonical domain
                    try:
                        domain = (
                            'es.wallapop.com' if name in ('__Host-next-auth.csrf-token', '__Secure-next-auth.callback-url') else '.wallapop.com'
                        )
                        self.session.cookies.set(name, value, domain=domain, path='/', secure=True)
                    except Exception:
                        self.session.cookies.set(name, value)

            # Log presence and lengths of key cookies for diagnostics
            try:
                sess_tok = normalized.get('__Secure-next-auth.session-token') or normalized.get('_Secure-next-auth.session-token')
                csrf_tok = normalized.get('__Host-next-auth.csrf-token') or normalized.get('_Host-next-auth.csrf-token')
                callback = normalized.get('__Secure-next-auth.callback-url') or normalized.get('_Secure-next-auth.callback-url')
                self.logger.info(
                    f"Cookie snapshot: session-token={'present' if sess_tok else 'missing'}"
                    + (f", len={len(sess_tok)}" if isinstance(sess_tok, str) else "")
                    + f"; csrf={'present' if csrf_tok else 'missing'}; callback={'present' if callback else 'missing'}"
                )
            except Exception:
                pass
            
            # Set realistic default headers for browser-like requests
            self.session.headers.update({
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'referer': 'https://es.wallapop.com/app/catalog/published',
                'origin': 'https://es.wallapop.com',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-gpc': '1',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'dnt': '1',
            })
            
            self.logger.info("Session loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load session: {e}")
            return False
    
    def _is_session_valid(self) -> bool:
        """Check if the stored session is still valid"""
        if not self.session_data:
            return False
        
        expires_str = self.session_data.get('expires')
        if not expires_str:
            return False
        
        try:
            expires = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
            return expires > datetime.now()
        except:
            return False
    
    def get_session_status(self) -> Dict[str, any]:
        """Get detailed session status information"""
        if not self.session_data:
            return {
                'valid': False,
                'reason': 'No session data loaded'
            }
        
        expires_str = self.session_data.get('expires')
        created_str = self.session_data.get('created')
        
        if not expires_str:
            return {
                'valid': False,
                'reason': 'No expiration date found'
            }
        
        try:
            expires = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
            created = datetime.fromisoformat(created_str.replace('Z', '+00:00')) if created_str else None
            now = datetime.now()
            
            if expires > now:
                days_left = (expires - now).days
                hours_left = ((expires - now).seconds // 3600)
                
                return {
                    'valid': True,
                    'expires': expires,
                    'created': created,
                    'days_left': days_left,
                    'hours_left': hours_left,
                    'expires_readable': expires.strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                return {
                    'valid': False,
                    'reason': 'Session has expired',
                    'expired_at': expires,
                    'expired_readable': expires.strftime('%Y-%m-%d %H:%M:%S')
                }
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Error parsing dates: {e}'
            }
    
    def needs_token_refresh(self) -> bool:
        """Check if access token needs refresh"""
        if not self.current_token or not self.token_expires_at:
            return True
        
        # Refresh if token expires within buffer time
        now = datetime.now()
        refresh_time = self.token_expires_at - timedelta(seconds=self.refresh_buffer_seconds)
        
        return now >= refresh_time
    
    def refresh_access_token(self) -> Tuple[bool, Optional[str]]:
        """
        Refresh the access token using persistent session
        
        Returns:
            Tuple[bool, Optional[str]]: (success, token_or_error_message)
        """
        if not self.session:
            return False, "No session available"
        
        try:
            self.logger.info("Refreshing access token...")
            
            # Use browser-like headers (important for some endpoints)
            headers = {
                'accept': 'application/json, text/plain, */*',
                # Include br,zstd like browser; server may ignore if unsupported
                'accept-encoding': 'gzip, deflate, br, zstd',
                'accept-language': 'en-US,en;q=0.9,ru;q=0.8,fr-FR;q=0.7,fr;q=0.6,pl;q=0.5,es;q=0.4',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'referer': 'https://es.wallapop.com/app/chat',
                'origin': 'https://es.wallapop.com',
                'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-gpc': '1',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'dnt': '1',
                'priority': 'u=1, i',
                'x-requested-with': 'XMLHttpRequest',
                # no 'origin' header in HAR for this GET
            }
            
            # Rely on session cookie handling (avoid manual Cookie header to not drop host-only cookies)
            headers_with_cookies = dict(headers)
            # Add x-csrf-token when available (extra parity)
            try:
                _csrf_tmp = self.session.cookies.get('__Host-next-auth.csrf-token', domain='es.wallapop.com', path='/')
                if _csrf_tmp:
                    headers_with_cookies['x-csrf-token'] = _csrf_tmp
            except Exception:
                pass
            try:
                jar = self.session.cookies
                cb = jar.get('__Secure-next-auth.callback-url', domain='es.wallapop.com', path='/')
                st = jar.get('__Secure-next-auth.session-token', domain='.wallapop.com', path='/') or jar.get('__Secure-next-auth.session-token', domain='es.wallapop.com', path='/')
                csrf = jar.get('__Host-next-auth.csrf-token', domain='es.wallapop.com', path='/')
                self.logger.debug(
                    f"Cookie jar snapshot: callback-url={'yes' if cb else 'no'}; session-token={'yes' if st else 'no'}; csrf={'yes' if csrf else 'no'}"
                )
            except Exception:
                pass

            # Install alias cookie names (some backends may read non-prefixed names)
            try:
                from requests.cookies import create_cookie
                alias_pairs = [
                    ('next-auth.session-token', '__Secure-next-auth.session-token'),
                    ('next-auth.csrf-token', '__Host-next-auth.csrf-token'),
                    ('next-auth.callback-url', '__Secure-next-auth.callback-url'),
                ]
                for alias, canon in alias_pairs:
                    if canon.endswith('session-token'):
                        val = self.session.cookies.get(canon, domain='.wallapop.com', path='/') or self.session.cookies.get(canon, domain='es.wallapop.com', path='/')
                    elif canon.endswith('csrf-token') or canon.endswith('callback-url'):
                        val = self.session.cookies.get(canon, domain='es.wallapop.com', path='/')
                    else:
                        val = self.session.cookies.get(canon)
                    if val and not self.session.cookies.get(alias):
                        ck = create_cookie(name=alias, value=val, domain='es.wallapop.com', path='/', secure=True)
                        self.session.cookies.set_cookie(ck)
            except Exception:
                pass

            # If we already have an accessToken cookie, surface it as X-RefreshSession (webapp behavior)
            try:
                existing_access = self.session.cookies.get('accessToken', domain='.wallapop.com', path='/')
                if existing_access:
                    headers_with_cookies['X-RefreshSession'] = existing_access
            except Exception:
                pass

            # Feature-flag warmups (as seen in HAR) to mirror browser initialization
            try:
                # Ensure callback-url points to app/chat like in HAR
                try:
                    self.session.cookies.set('__Secure-next-auth.callback-url', 'https%3A%2F%2Fes.wallapop.com%2Fapp%2Fchat', domain='es.wallapop.com', path='/', secure=True)
                except Exception:
                    pass
                ff_headers = dict(headers_with_cookies)
                ff_headers['referer'] = 'https://es.wallapop.com/app/chat'
                ff_headers['sec-fetch-site'] = 'cross-site'
                ff_headers.pop('origin', None)
                for ff in (
                    'https://feature-flag.wallapop.com/api/v3/featureflag?featureFlags=tns_platform_keycloak_web_email_login',
                    'https://feature-flag.wallapop.com/api/v3/featureflag?featureFlags=tns_platform_keycloak_web_disable_recaptcha_login',
                ):
                    with contextlib.suppress(Exception):
                        self.session.get(ff, headers=ff_headers, timeout=10)
            except Exception:
                pass

            # Warm up app/chat as referer context (per HAR)
            try:
                self.session.get('https://es.wallapop.com/app/chat', headers=headers_with_cookies, timeout=10)
            except Exception:
                pass

            # Also hit /api/auth/session before federated-session (observed in HAR)
            try:
                self.session.get('https://es.wallapop.com/api/auth/session', headers=headers_with_cookies, timeout=10)
            except Exception:
                pass

            # First federated-session call with cache revalidation header (per HAR presence of If-None-Match)
            headers_first = dict(headers_with_cookies)
            # Use an ETag value observed in HAR to force content return versus minimal {}
            headers_first['if-none-match'] = '"5c00u7sozwqp"'
            # Add cache-busting param to avoid CloudFront cached minimal body
            import time as _time
            response = self.session.get(self.token_refresh_url, headers=headers_first, params={'_': str(int(_time.time()*1000))})
            
            def _extract_token_from_json(data: Dict[str, any]) -> Optional[str]:
                if not isinstance(data, dict):
                    return None
                if 'token' in data and data['token']:
                    return data['token']
                if 'accessToken' in data and data['accessToken']:
                    return data['accessToken']
                return None

            def _extract_token_from_response(resp: requests.Response) -> Optional[str]:
                # Try response.cookies first
                try:
                    v = resp.cookies.get('accessToken')
                    if v:
                        return v
                except Exception:
                    pass
                # Then iterate all Set-Cookie headers
                try:
                    headers_list = []
                    # urllib3 header dict
                    try:
                        headers_list = resp.raw.headers.getlist('Set-Cookie')  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    # http.client.HTTPMessage
                    try:
                        orig = getattr(resp.raw, '_original_response', None)
                        if orig is not None:
                            hdrs = getattr(orig, 'headers', None)
                            if hdrs is not None:
                                get_all = getattr(hdrs, 'get_all', None)
                                if callable(get_all):
                                    headers_list = headers_list + (get_all('Set-Cookie') or [])
                    except Exception:
                        pass
                    # Fallback single header
                    if not headers_list:
                        single = resp.headers.get('Set-Cookie')
                        if single:
                            headers_list = [single]
                    if headers_list:
                        self.logger.debug(f"Set-Cookie headers present: {len(headers_list)}")
                        # Log cookie names for diagnostics
                        try:
                            names = []
                            for sc in headers_list:
                                nv = sc.split('=', 1)[0]
                                names.append(nv.strip())
                            self.logger.debug(f"Set-Cookie names: {names}")
                        except Exception:
                            pass
                    for sc in headers_list:
                        if 'accessToken=' in sc:
                            part = sc.split('accessToken=', 1)[1]
                            return part.split(';', 1)[0]
                except Exception:
                    pass
                return None

            def _extract_token_from_cookiejar(jar: requests.cookies.RequestsCookieJar) -> Optional[str]:
                try:
                    for c in jar:
                        if c.name == 'accessToken' and c.value:
                            return c.value
                except Exception:
                    pass
                try:
                    return jar.get('accessToken')
                except Exception:
                    return None
            
            def _handle_success(token: str, extra_info: Optional[Dict[str, any]] = None) -> Tuple[bool, Optional[str]]:
                self.current_token = token
                # Set token expiration (5 minutes from now)
                self.token_expires_at = datetime.now() + timedelta(minutes=self.token_lifetime_minutes)
                if extra_info and 'expires' in extra_info:
                    self.logger.info(f"Session expires: {extra_info.get('expires')}")
                self.logger.info("Token refreshed successfully")
                self.logger.info(f"Token expires at: {self.token_expires_at}")
                # Also set cookie (some flows expect it)
                try:
                    self.session.cookies.set('accessToken', token, domain='.wallapop.com')
                except Exception:
                    pass
                return True, token
            
            # Parse federated-session response
            if response.status_code == 200:
                try:
                    data = response.json() if response.text else {}
                except json.JSONDecodeError:
                    data = {}
                token = _extract_token_from_json(data)
                if token:
                    return _handle_success(token, data)
                # Some flows set token only as cookie without JSON body
                access_cookie = _extract_token_from_response(response) or _extract_token_from_cookiejar(self.session.cookies)
                if access_cookie:
                    self.logger.info("Token obtained from accessToken cookie after federated-session")
                    return _handle_success(access_cookie)
                try:
                    hdr_names = list(response.headers.keys())[:20]
                    jar_names = [c.name for c in self.session.cookies]
                    self.logger.warning(f"No token in federated-session response: {data}")
                    self.logger.debug(f"Response headers (first 20): {hdr_names}")
                    self.logger.debug(f"Cookie jar names: {jar_names}")
                except Exception:
                    self.logger.warning(f"No token in federated-session response: {data}")
                # Fallback: call federated-session with session token as query param
                # Support both single and double underscore variants
                session_cookie = (
                    self.session.cookies.get('_Secure-next-auth.session-token', domain='.wallapop.com', path='/')
                    or self.session.cookies.get('__Secure-next-auth.session-token', domain='.wallapop.com', path='/')
                    or self.session.cookies.get('_Secure-next-auth.session-token', domain='es.wallapop.com', path='/')
                    or self.session.cookies.get('__Secure-next-auth.session-token', domain='es.wallapop.com', path='/')
                )
                if session_cookie:
                    try:
                        resp_q = self.session.get(self.token_refresh_url, headers=headers_with_cookies, params={'token': session_cookie})
                        if resp_q.status_code == 200:
                            try:
                                d2 = resp_q.json() if resp_q.text else {}
                            except json.JSONDecodeError:
                                d2 = {}
                            tok2 = _extract_token_from_json(d2)
                            if tok2:
                                self.logger.info("Token obtained from federated-session?token=...")
                                return _handle_success(tok2, d2)
                            # Check cookie again
                            acc2 = _extract_token_from_response(resp_q) or _extract_token_from_cookiejar(self.session.cookies)
                            if acc2:
                                self.logger.info("Token cookie set after federated-session?token=...")
                                return _handle_success(acc2)
                    except Exception as qe:
                        self.logger.debug(f"Query token fallback error: {qe}")
            elif response.status_code == 401:
                error_msg = "Session cookies have expired - need fresh login"
                self.logger.error(error_msg)
                return False, error_msg
            else:
                self.logger.warning(f"federated-session returned {response.status_code}: {response.text[:200]}")

            # Provoke refresh path AFTER first federated-session (per HAR)
            try:
                csrf = self.session.cookies.get('__Host-next-auth.csrf-token', domain='es.wallapop.com', path='/')
                provoke_headers = dict(headers_with_cookies)
                provoke_headers['referer'] = 'https://es.wallapop.com/app/chat'
                provoke_headers['origin'] = 'https://es.wallapop.com'
                if csrf:
                    provoke_headers['x-csrf-token'] = csrf
                device_id = self.session.cookies.get('device_id')
                if device_id:
                    provoke_headers['X-DeviceID'] = device_id
                provoke_headers['DeviceOS'] = '0'
                provoke_headers['X-DeviceOS'] = '0'
                provoke_headers['X-AppVersion'] = '810840'
                provoke_headers['sec-fetch-site'] = 'same-site'
                provoke_headers['sec-fetch-mode'] = 'cors'
                provoke_headers['sec-fetch-dest'] = 'empty'
                for purl in (
                    'https://api.wallapop.com/api/v3/instant-messaging/messages/unread',
                    'https://api.wallapop.com/api/v3/users/me/',
                ):
                    with contextlib.suppress(Exception):
                        self.session.get(purl, headers=provoke_headers, timeout=10)
            except Exception:
                pass

            # Second federated-session attempt (mirrors HAR pattern)
            response = self.session.get(self.token_refresh_url, headers=headers_with_cookies, params={'_': str(int(_time.time()*1000))})

            # Try HTTP/2 call via httpx as a fallback if available; mirror headers and cookies
            if self._http2_available:
                try:
                    import httpx  # type: ignore
                    # Build cookie dict from jar
                    jar_cookies = {}
                    for c in self.session.cookies:
                        jar_cookies[c.name] = c.value
                    with httpx.Client(http2=True, headers=headers_with_cookies, cookies=jar_cookies, timeout=10.0) as hx:
                        hresp = hx.get(self.token_refresh_url)
                        if hresp.status_code == 200:
                            try:
                                hdata = hresp.json() if hresp.text else {}
                            except Exception:
                                hdata = {}
                            htok = hdata.get('token') or hdata.get('accessToken')
                            if htok:
                                self.logger.info("Token obtained from federated-session over HTTP/2 (httpx)")
                                return _handle_success(htok, hdata)
                            # Check cookies from httpx response
                            acc = hresp.cookies.get('accessToken')
                            if acc:
                                self.logger.info("Token cookie from httpx HTTP/2 response")
                                return _handle_success(acc)
                except Exception as e:
                    self.logger.debug(f"httpx HTTP/2 fallback error: {e}")
            
            # Fallback attempts (seen in HAR/old client)
            fallback_endpoints = [
                ('https://es.wallapop.com/api/auth/session', 'session'),
                ('https://es.wallapop.com/api/auth/token', 'token'),
                ('https://es.wallapop.com/api/auth/refresh', 'refresh'),
                ('https://es.wallapop.com/api/v3/me', 'me'),
                ('https://es.wallapop.com/api/v3/general/navigation', 'navigation'),
                # Mimic webapp navigations which, per HAR, precede successful token issuance
                ('https://es.wallapop.com/app/chat', 'app_chat'),
                ('https://es.wallapop.com/app/catalog/published', 'app_catalog_published'),
            ]
            for url, name in fallback_endpoints:
                try:
                    resp = self.session.get(url, headers=headers_with_cookies)
                    if resp.status_code == 200:
                        try:
                            d = resp.json() if resp.text else {}
                        except json.JSONDecodeError:
                            d = {}
                        token = _extract_token_from_json(d)
                        if token:
                            self.logger.info(f"Token obtained from {name} endpoint")
                            return _handle_success(token, d)
                        # Sometimes hitting these endpoints sets cookies used by federated-session
                        current_access_cookie = _extract_token_from_response(resp) or _extract_token_from_cookiejar(self.session.cookies)
                        if current_access_cookie:
                            self.logger.info(f"Found accessToken cookie after hitting {name} endpoint")
                            return _handle_success(current_access_cookie)
                    else:
                        self.logger.debug(f"{name} endpoint status {resp.status_code}")
                except Exception as e:
                    self.logger.debug(f"{name} endpoint error: {e}")
            
            # As a last resort, try federated-session once more after fallbacks
            response2 = self.session.get(self.token_refresh_url, headers=headers_with_cookies)
            if response2.status_code == 200:
                try:
                    data2 = response2.json() if response2.text else {}
                except json.JSONDecodeError:
                    data2 = {}
                token2 = _extract_token_from_json(data2)
                if token2:
                    return _handle_success(token2, data2)
                # Final cookie check from response/jar
                acc3 = _extract_token_from_response(response2) or _extract_token_from_cookiejar(self.session.cookies)
                if acc3:
                    return _handle_success(acc3)
            # Webapp also references an access refresh endpoint under API v3; try it explicitly
            try:
                refresh_url = 'https://api.wallapop.com/api/v3/access/refresh'
                headers_refresh = dict(headers_with_cookies)
                # Prefer deviceAccessToken cookie if present; fallback to device_id
                device_access = None
                try:
                    device_access = self.session.cookies.get('deviceAccessToken', domain='.wallapop.com', path='/')
                except Exception:
                    device_access = None
                if device_access:
                    headers_refresh['X-DeviceToken'] = device_access
                elif device_id:
                    headers_refresh['X-DeviceToken'] = device_id
                # Send both referer/origin as webapp
                headers_refresh['referer'] = 'https://es.wallapop.com/app/catalog/published'
                headers_refresh['origin'] = 'https://es.wallapop.com'
                headers_refresh['content-type'] = 'application/json'
                # Try POST first (405 observed on GET)
                rresp = self.session.post(refresh_url, headers=headers_refresh, json={})
                if rresp.status_code == 405:
                    # Fallback to GET if POST not allowed
                    rresp = self.session.get(refresh_url, headers=headers_refresh)
                if rresp.status_code == 200:
                    try:
                        rdata = rresp.json() if rresp.text else {}
                    except json.JSONDecodeError:
                        rdata = {}
                    rtoken = _extract_token_from_json(rdata)
                    if rtoken:
                        self.logger.info("Token obtained from api/v3/access/refresh")
                        return _handle_success(rtoken, rdata)
                    racc = _extract_token_from_response(rresp) or _extract_token_from_cookiejar(self.session.cookies)
                    if racc:
                        self.logger.info("Token cookie set by api/v3/access/refresh")
                        return _handle_success(racc)
                else:
                    self.logger.debug(f"access/refresh status {rresp.status_code}")
            except Exception as e:
                self.logger.debug(f"access/refresh error: {e}")
            # One more nudge: call /api/v3/users/me which often forces access token refresh
            try:
                csrf = self.session.cookies.get('__Host-next-auth.csrf-token')
                headers_nudge = dict(headers_with_cookies)
                if csrf:
                    headers_nudge['x-csrf-token'] = csrf
                nudge = self.session.get('https://api.wallapop.com/api/v3/users/me/', headers=headers_nudge)
                if nudge.status_code == 200:
                    nudge_token = _extract_token_from_response(nudge) or _extract_token_from_cookiejar(self.session.cookies)
                    if nudge_token:
                        self.logger.info("Token obtained after nudge /api/v3/users/me")
                        return _handle_success(nudge_token)
                # Retry federated-session once more after nudge
                response3 = self.session.get(self.token_refresh_url, headers=headers_with_cookies)
                if response3.status_code == 200:
                    try:
                        data3 = response3.json() if response3.text else {}
                    except json.JSONDecodeError:
                        data3 = {}
                    token3 = _extract_token_from_json(data3)
                    if token3:
                        return _handle_success(token3, data3)
                    token3c = _extract_token_from_response(response3) or _extract_token_from_cookiejar(self.session.cookies)
                    if token3c:
                        return _handle_success(token3c)
            except Exception:
                pass
            
            # Final attempt: try a headless browser to mimic the app precisely
            success, token = self._browser_fallback_fetch_token()
            if success and token:
                return _handle_success(token)
            error_msg = f"Token refresh failed after fallbacks: {response.status_code}"
            self.logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Token refresh error: {e}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def get_valid_token(self) -> Tuple[bool, Optional[str]]:
        """
        Get a valid access token, refreshing if necessary
        
        Returns:
            Tuple[bool, Optional[str]]: (success, token_or_error_message)
        """
        if not self.session:
            if not self.load_session():
                return False, "Failed to load session"
        
        # Check if we need to refresh the token
        if self.needs_token_refresh():
            return self.refresh_access_token()
        
        # Return current token if still valid
        if self.current_token:
            return True, self.current_token
        
        # First time - need to get initial token
        return self.refresh_access_token()

    def load_from_cookies_dict(self, cookies: Dict[str, str]) -> bool:
        """Initialize a requests session from a cookies dict (no file read/write).

        This mirrors load_session() cookie normalization and header setup to allow
        validating ad-hoc cookies (e.g., from a root cookies.json file) without persisting yet.
        """
        try:
            self.session = requests.Session()
            # Sanitize values
            sanitized: Dict[str, str] = {}
            for k, v in cookies.items():
                if isinstance(v, str):
                    vv = v.strip()
                    if (vv.startswith('"') and vv.endswith('"')) or (vv.startswith("'") and vv.endswith("'")):
                        vv = vv[1:-1]
                    sanitized[k] = vv
                else:
                    sanitized[k] = v
            cookies = sanitized

            # Normalize aliases
            normalized: Dict[str, str] = dict(cookies)
            mapping_pairs = [
                ("_Secure-next-auth.session-token", "__Secure-next-auth.session-token"),
                ("_Host-next-auth.csrf-token", "__Host-next-auth.csrf-token"),
                ("_Secure-next-auth.callback-url", "__Secure-next-auth.callback-url"),
            ]
            for single, double in mapping_pairs:
                if single in cookies and double not in normalized:
                    normalized[double] = cookies[single]
                if double in cookies and single not in normalized:
                    normalized[single] = cookies[double]

            from requests.cookies import create_cookie
            def should_set_cookie(name: str) -> bool:
                if name.startswith('_Secure-next-auth.') or name.startswith('_Host-next-auth.'):
                    return False
                return True

            for name, value in normalized.items():
                if not should_set_cookie(name):
                    continue
                try:
                    cookies_to_set = []
                    # Canonical domains per browser behavior
                    if name == '__Host-next-auth.csrf-token' or name == '__Secure-next-auth.callback-url':
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='es.wallapop.com', path='/', secure=True))
                    elif name == '__Secure-next-auth.session-token' or name == 'device_id' or name == 'accessToken':
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='.wallapop.com', path='/', secure=True))
                    elif name.startswith('__Host-'):
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='es.wallapop.com', path='/', secure=True))
                    else:
                        cookies_to_set.append(create_cookie(name=name, value=value, domain='.wallapop.com', path='/', secure=True))
                    # Clear duplicates across domains/paths for this name
                    try:
                        for c in list(self.session.cookies):
                            if c.name == name:
                                with contextlib.suppress(Exception):
                                    self.session.cookies.clear(domain=c.domain, path=c.path, name=c.name)
                    except Exception:
                        pass
                    for ck in cookies_to_set:
                        self.session.cookies.set_cookie(ck)
                except Exception:
                    try:
                        domain = 'es.wallapop.com' if name in ('__Host-next-auth.csrf-token', '__Secure-next-auth.callback-url') else '.wallapop.com'
                        self.session.cookies.set(name, value, domain=domain, path='/', secure=True)
                    except Exception:
                        self.session.cookies.set(name, value)

            # Set default headers
            self.session.headers.update({
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en-US,en;q=0.9',
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'referer': 'https://es.wallapop.com/app/catalog/published',
                'origin': 'https://es.wallapop.com',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-gpc': '1',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'dnt': '1',
            })

            # Record ephemeral session_data (not persisted)
            now = datetime.now()
            self.session_data = {
                'cookies': normalized,
                'created': now.isoformat(),
                'expires': (now + timedelta(days=30)).isoformat(),
                'source': 'in-memory',
            }
            return True
        except Exception as e:
            self.logger.error(f"Failed to load cookies dict: {e}")
            return False

    def _browser_fallback_fetch_token(self) -> Tuple[bool, Optional[str]]:
        """Use undetected-chromedriver in headless mode to hit federated-session and harvest accessToken.

        Returns (success, token)
        """
        if not os.getenv('WALLAPOP_USE_BROWSER_FALLBACK', '1'):
            return False, None
        try:
            import undetected_chromedriver as uc  # type: ignore
            from selenium.webdriver.common.by import By  # type: ignore
            from selenium.webdriver.common.desired_capabilities import DesiredCapabilities  # type: ignore
        except Exception as e:
            self.logger.debug(f"Browser fallback unavailable: {e}")
            return False, None

        try:
            self.logger.info("Attempting browser fallback to refresh token...")
            options = uc.ChromeOptions()
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--lang=es-ES,es')
            options.add_argument('--window-size=1280,900')
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36')
            caps = DesiredCapabilities.CHROME
            caps["pageLoadStrategy"] = "eager"
            driver = uc.Chrome(options=options, desired_capabilities=caps)
            try:
                # Open domain to allow setting cookies
                driver.get('https://es.wallapop.com/')
                # Set essential cookies from our session jar
                def add_cookie(name: str, value: str):
                    try:
                        # Host-only: do not set domain
                        driver.add_cookie({'name': name, 'value': value, 'path': '/', 'secure': True})
                    except Exception:
                        try:
                            driver.add_cookie({'name': name, 'value': value})
                        except Exception:
                            pass
                jar = self.session.cookies if self.session else None
                names = [
                    '__Secure-next-auth.session-token',
                    '__Host-next-auth.csrf-token',
                    '__Secure-next-auth.callback-url',
                    'device_id',
                ]
                for nm in names:
                    try:
                        if not jar:
                            val = None
                        elif nm == '__Secure-next-auth.session-token':
                            val = jar.get(nm, domain='.wallapop.com', path='/') or jar.get(nm, domain='es.wallapop.com', path='/')
                        elif nm in ('__Host-next-auth.csrf-token', '__Secure-next-auth.callback-url'):
                            val = jar.get(nm, domain='es.wallapop.com', path='/')
                        else:
                            val = jar.get(nm, domain='.wallapop.com', path='/')
                        if val:
                            add_cookie(nm, val)
                    except Exception:
                        pass
                # Navigate to app page
                driver.get('https://es.wallapop.com/app/chat')
                # Trigger federated-session via XHR from page context to mirror HAR
                try:
                    js = """
                    return fetch('/api/auth/federated-session', {
                        method: 'GET',
                        headers: {
                            'accept': 'application/json, text/plain, */*',
                        },
                        credentials: 'include'
                    }).then(r => r.text()).then(t => ({ ok: true, text: t })).catch(e => ({ ok: false, error: String(e) }));
                    """
                    res = driver.execute_script(js)
                    if isinstance(res, dict) and res.get('ok') and res.get('text'):
                        try:
                            data = json.loads(res['text'])
                            token = data.get('token') or data.get('accessToken')
                            if token:
                                try:
                                    self.session.cookies.set('accessToken', token, domain='.wallapop.com', path='/')
                                except Exception:
                                    pass
                                self.logger.info("Token obtained via browser fallback (XHR)")
                                return True, token
                        except Exception:
                            pass
                except Exception:
                    pass
                # Inspect cookies
                cookies = {c.get('name'): c.get('value') for c in driver.get_cookies()}
                token = cookies.get('accessToken')
                if not token:
                    # Try document.cookie as a last resort
                    try:
                        dc = driver.execute_script('return document.cookie') or ''
                        for part in dc.split(';'):
                            part = part.strip()
                            if part.startswith('accessToken='):
                                token = part.split('=', 1)[1]
                                break
                    except Exception:
                        pass
                if token:
                    try:
                        # persist into our requests session too
                        self.session.cookies.set('accessToken', token, domain='.wallapop.com', path='/')
                    except Exception:
                        pass
                    self.logger.info("Token obtained via browser fallback")
                    return True, token
                return False, None
            finally:
                with contextlib.suppress(Exception):
                    driver.quit()
        except Exception as e:
            self.logger.debug(f"Browser fallback failed: {e}")
            return False, None
    
    def make_authenticated_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an authenticated request with automatic token refresh
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for requests
        
        Returns:
            requests.Response: The response object
        """
        # Get valid token
        success, token_or_error = self.get_valid_token()
        if not success:
            raise Exception(f"Failed to get valid token: {token_or_error}")
        
        # Prepare headers
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {token_or_error}'
        kwargs['headers'] = headers
        
        # Make request
        response = self.session.request(method, url, **kwargs)
        
        # If we get 401, try refreshing token once
        if response.status_code == 401:
            self.logger.info("Got 401, attempting token refresh...")
            
            success, new_token_or_error = self.refresh_access_token()
            if success:
                # Retry with new token
                headers['Authorization'] = f'Bearer {new_token_or_error}'
                kwargs['headers'] = headers
                response = self.session.request(method, url, **kwargs)
            else:
                self.logger.error(f"Token refresh failed: {new_token_or_error}")
        
        return response
    
    def cleanup_expired_session(self):
        """Remove expired session file"""
        try:
            if self.session_file.exists():
                self.session_file.unlink()
                self.logger.info("Removed expired session file")
        except Exception as e:
            self.logger.error(f"Failed to remove session file: {e}")
    
    def get_session_summary(self) -> str:
        """Get a human-readable session summary"""
        status = self.get_session_status()
        
        if status['valid']:
            days = status['days_left']
            hours = status['hours_left']
            expires = status['expires_readable']
            
            if days > 0:
                return f"Session valid for {days} days (expires {expires})"
            else:
                return f"Session valid for {hours} hours (expires {expires})"
        else:
            return f"Session invalid: {status['reason']}"

# Backwards compatibility wrapper
class SessionManager(SessionPersistenceManager):
    """Legacy session manager for backwards compatibility"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def save_session(self, cookies_dict: Dict[str, str]):
        """Save session data (legacy method)"""
        # This would typically be called by the cookie extraction guide
        expires = datetime.now() + timedelta(days=30)
        
        session_data = {
            'cookies': cookies_dict,
            'created': datetime.now().isoformat(),
            'expires': expires.isoformat(),
            'version': '1.0'
        }
        
        try:
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save session: {e}")
            return False