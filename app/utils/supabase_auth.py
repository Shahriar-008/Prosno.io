"""
Supabase Auth Helper for Prosno.io

Lightweight wrapper around Supabase Auth REST API using requests.
No heavy SDK dependencies needed - just uses the GoTrue REST endpoints.
"""
import requests
from urllib.parse import urlencode


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

    def sign_up(self, email, password):
        """Register a new user.

        Returns dict with 'user' and optionally 'session' keys.
        Raises SupabaseAuthError on failure.
        """
        resp = requests.post(
            f"{self.base_url}/signup",
            json={"email": email, "password": password},
            headers=self.headers,
            timeout=15
        )
        data = resp.json()
        if resp.status_code >= 400:
            raise SupabaseAuthError(data.get('msg') or data.get('error_description') or data.get('message', 'Registration failed'))
        return data

    def sign_in(self, email, password):
        """Sign in with email and password.

        Returns dict with 'user' and 'session' keys (including access_token).
        Raises SupabaseAuthError on failure.
        """
        resp = requests.post(
            f"{self.base_url}/token?grant_type=password",
            json={"email": email, "password": password},
            headers=self.headers,
            timeout=15
        )
        data = resp.json()
        if resp.status_code >= 400:
            raise SupabaseAuthError(data.get('msg') or data.get('error_description') or data.get('message', 'Login failed'))
        return data

    def sign_out(self, access_token):
        """Sign out a user by invalidating their token."""
        headers = {**self.headers, 'Authorization': f'Bearer {access_token}'}
        try:
            requests.post(
                f"{self.base_url}/logout",
                headers=headers,
                timeout=10
            )
        except Exception:
            pass  # Best effort

    def get_user(self, access_token):
        """Get user details from access token."""
        headers = {**self.headers, 'Authorization': f'Bearer {access_token}'}
        resp = requests.get(
            f"{self.base_url}/user",
            headers=headers,
            timeout=10
        )
        if resp.status_code >= 400:
            return None
        return resp.json()

    # ── OAuth (Google Sign-In) ─────────────────────────────────

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
            
        return f"{self.base_url}/authorize?{urlencode(params)}"

    def exchange_code_for_session(self, code, code_verifier=None):
        """Exchange an OAuth authorization code for a user session."""
        payload = {
            "code": code,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            payload['code_verifier'] = code_verifier

        resp = requests.post(
            f"{self.base_url}/token",
            json=payload,
            headers=self.headers,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code >= 400:
            raise SupabaseAuthError(
                data.get('msg')
                or data.get('error_description')
                or data.get('message', 'OAuth code exchange failed')
            )
        return data


class SupabaseAuthError(Exception):
    """Raised when a Supabase Auth API call fails."""
    pass
