"""
Supabase Auth Helper for Prosno.io

Lightweight wrapper around Supabase Auth REST API using requests.
No heavy SDK dependencies needed - just uses the GoTrue REST endpoints.
"""
import requests
import logging
from urllib.parse import urlencode, urlparse

# Configure logger
logger = logging.getLogger(__name__)

class SupabaseAuth:
    """Simple Supabase Auth client using REST API."""

    def __init__(self, supabase_url, supabase_key):
        if not supabase_url.startswith(('http://', 'https://')):
            raise ValueError(
                f"Invalid SUPABASE_URL: '{supabase_url}'. "
                "It must be an HTTP URL (e.g., https://xyz.supabase.co), "
                "not a database connection string."
            )
        self.supabase_url = supabase_url.rstrip('/')
        self.base_url = f"{self.supabase_url}/auth/v1"
        self.api_key = supabase_key
        self.headers = {
            'apikey': supabase_key,
            'Content-Type': 'application/json',
        }

    def _log_request(self, method, url, data=None):
        """Log request details (redacting sensitive info)."""
        safe_data = data.copy() if data else {}
        if 'password' in safe_data:
            safe_data['password'] = '********'
        logger.info(f"Supabase Auth Request: {method} {url} | Data: {safe_data}")

    def _log_response(self, response):
        """Log response details."""
        try:
            body = response.json()
        except Exception:
            body = response.text
        
        level = logging.INFO if response.status_code < 400 else logging.ERROR
        logger.log(level, f"Supabase Auth Response: {response.status_code} | Body: {body}")

    def _request(self, method, endpoint, json=None, headers=None):
        """Internal helper to make requests with logging."""
        url = f"{self.base_url}/{endpoint}"
        req_headers = {**self.headers, **(headers or {})}
        
        self._log_request(method, url, json)
        
        try:
            resp = requests.request(
                method,
                url,
                json=json,
                headers=req_headers,
                timeout=15
            )
            self._log_response(resp)
            return resp
        except Exception as e:
            logger.error(f"Supabase Auth Network Error: {e}")
            raise

    def sign_up(self, email, password):
        """Register a new user.

        Returns dict with 'user' and optionally 'session' keys.
        Raises SupabaseAuthError on failure.
        """
        resp = self._request('POST', 'signup', json={"email": email, "password": password})
        data = resp.json()
        logger.debug(f"Sign-up raw response (status={resp.status_code}): {data}")
        if resp.status_code >= 400:
            error_msg = data.get('msg') or data.get('error_description') or data.get('message', 'Registration failed')
            logger.error(f"Sign-up failed: {error_msg} | Full response: {data}")
            raise SupabaseAuthError(error_msg)
        return data

    def sign_in(self, email, password):
        """Sign in with email and password.

        Returns dict with 'user' and 'session' keys (including access_token).
        Raises SupabaseAuthError on failure.
        """
        resp = self._request('POST', 'token?grant_type=password', json={"email": email, "password": password})
        data = resp.json()
        logger.debug(f"Sign-in raw response (status={resp.status_code}): {data}")
        if resp.status_code >= 400:
            error_msg = data.get('msg') or data.get('error_description') or data.get('message', 'Login failed')
            logger.error(f"Sign-in failed: {error_msg} | Full response: {data}")
            raise SupabaseAuthError(error_msg)
        return data

    def sign_out(self, access_token):
        """Sign out a user by invalidating their token."""
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            self._request('POST', 'logout', headers=headers)
        except Exception:
            pass  # Best effort

    def get_user(self, access_token):
        """Get user details from access token."""
        headers = {'Authorization': f'Bearer {access_token}'}
        resp = self._request('GET', 'user', headers=headers)
        if resp.status_code >= 400:
            return None
        return resp.json()

    # ── OAuth (Google Sign-In) ─────────────────────────────────
    
    def get_google_login_url(self, redirect_to, code_challenge=None):
        """Build the Supabase OAuth URL that redirects the user to Google.

        Args:
            redirect_to: The URL Supabase should redirect to after Google consent
            code_challenge: PKCE code challenge (optional but Recommended)

        Returns:
            The full authorize URL to redirect the browser to.
        """
        params = {
            'provider': 'google',
            'redirect_to': redirect_to,
        }
        if code_challenge:
            params['code_challenge'] = code_challenge
            params['code_challenge_method'] = 's256'
            
        url = f"{self.base_url}/authorize?{urlencode(params)}"
        logger.info(f"Generated OAuth URL: {url}")
        return url

    def exchange_code_for_session(self, code, code_verifier=None):
        """Exchange an OAuth authorization code for a user session."""
        payload = {
            "auth_code": code,
        }
        if code_verifier:
            payload['code_verifier'] = code_verifier

        # grant_type must be a query parameter, not in the JSON body
        # (matching how sign_in uses 'token?grant_type=password')
        resp = self._request('POST', 'token?grant_type=pkce', json=payload)
        data = resp.json()
        logger.debug(f"Code exchange raw response (status={resp.status_code}): {data}")
        if resp.status_code >= 400:
            error_msg = (
                data.get('msg')
                or data.get('error_description')
                or data.get('message', 'OAuth code exchange failed')
            )
            logger.error(f"Code exchange failed: {error_msg} | Full response: {data}")
            raise SupabaseAuthError(error_msg)
        return data


class SupabaseAuthError(Exception):
    """Raised when a Supabase Auth API call fails."""
    pass

