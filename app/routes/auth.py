"""
Auth routes for Prosno.io (Public User Authentication via Supabase REST API)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from urllib.parse import urlparse, urljoin
from app import csrf, limiter
from app.utils.supabase_auth import SupabaseAuthError

auth_bp = Blueprint('auth', __name__)


def is_safe_url(target: str) -> bool:
    """Validate redirect URL to prevent open redirect attacks."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def get_supabase_client():
    """Get Supabase Auth client from app context."""
    return current_app.config.get('SUPABASE_CLIENT')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    """Public user login via Supabase Auth"""
    # If already logged in via Supabase session
    if session.get('user'):
        return redirect(url_for('main.generate'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'error')
            return render_template('main/login.html')

        supabase = get_supabase_client()
        if not supabase:
            flash('Authentication service is not configured. Please contact the administrator.', 'error')
            return render_template('main/login.html')

        try:
            data = supabase.sign_in(email, password)

            # Store user info in Flask session
            user_data = data.get('user', {})
            session['user'] = {
                'id': user_data.get('id'),
                'email': user_data.get('email', email),
                'username': user_data.get('user_metadata', {}).get('username', ''),
                'access_token': data.get('access_token'),
            }
            session.permanent = True

            flash('Welcome back! You are now logged in.', 'success')

            # Redirect to next page or generate (validate to prevent open redirect)
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('main.generate'))

        except SupabaseAuthError as e:
            error_msg = str(e)
            current_app.logger.error(f"Supabase login error: {error_msg}")
            if 'Invalid login credentials' in error_msg:
                flash('Invalid email or password.', 'error')
            elif 'Email not confirmed' in error_msg:
                flash('Please confirm your email before logging in. Check your inbox.', 'warning')
            else:
                # Show actual error in debug mode for easier diagnosis
                if current_app.debug:
                    flash(f'Login failed: {error_msg}', 'error')
                else:
                    flash('Login failed. Please try again.', 'error')
        except Exception as e:
            current_app.logger.error(f"Login error: {e}")
            if current_app.debug:
                flash(f'Login error: {e}', 'error')
            else:
                flash('Login failed. Please try again.', 'error')

    return render_template('main/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    """Public user registration via Supabase Auth"""
    if session.get('user'):
        return redirect(url_for('main.generate'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        username = request.form.get('username', '').strip()

        # Validation
        if not email or not password or not username:
            flash('Please fill in all fields.', 'error')
            return render_template('main/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('main/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return render_template('main/register.html')

        supabase = get_supabase_client()
        if not supabase:
            flash('Authentication service is not configured. Please contact the administrator.', 'error')
            return render_template('main/register.html')

        try:
            data = supabase.sign_up(email, password, user_metadata={'username': username})
            current_app.logger.info(f"Sign-up response keys: {list(data.keys())}")

            # Handle both Supabase response formats:
            # - Auto-confirm ON:  {"access_token": "...", "user": {...}}
            # - Auto-confirm OFF: {"id": "...", "email": "...", "identities": [...], ...}
            if 'user' in data:
                user_data = data['user']
            elif 'id' in data:
                # User data is at the top level (email confirmation enabled)
                user_data = data
            else:
                user_data = {}

            identities = user_data.get('identities', [])
            user_id = user_data.get('id')

            if user_id and identities:
                # Check if session was returned (auto-confirm enabled)
                if data.get('access_token'):
                    session['user'] = {
                        'id': user_data.get('id'),
                        'email': user_data.get('email', email),
                        'username': username,
                        'access_token': data.get('access_token'),
                    }
                    session.permanent = True
                    flash('Account created successfully! Welcome!', 'success')
                    return redirect(url_for('main.generate'))
                else:
                    flash('Account created! Please check your email to confirm, then log in.', 'success')
                    return redirect(url_for('auth.login'))
            elif user_id and not identities:
                # User already exists (Supabase returns empty identities for duplicates)
                flash('An account with this email already exists. Please log in.', 'error')
            else:
                current_app.logger.error(f"Unexpected sign-up response: {data}")
                flash('Registration failed. Please try again.', 'error')

        except SupabaseAuthError as e:
            error_msg = str(e)
            current_app.logger.error(f"Supabase registration error: {error_msg}")
            if 'already registered' in error_msg.lower():
                flash('An account with this email already exists. Please log in.', 'error')
            elif 'password' in error_msg.lower():
                flash('Password is too weak. Use at least 6 characters.', 'error')
            else:
                # Show actual error in debug mode
                if current_app.debug:
                    flash(f'Registration failed: {error_msg}', 'error')
                else:
                    flash('Registration failed. Please try again.', 'error')
        except Exception as e:
            current_app.logger.error(f"Registration error: {e}")
            if current_app.debug:
                flash(f'Registration error: {e}', 'error')
            else:
                flash('Registration failed. Please try again.', 'error')

    return render_template('main/register.html')


@auth_bp.route('/logout')
def logout():
    """Log out public user (clear Supabase session)"""
    supabase = get_supabase_client()
    user = session.get('user')

    if supabase and user and user.get('access_token'):
        supabase.sign_out(user['access_token'])

    session.pop('user', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))


# ── Google OAuth ──────────────────────────────────────────────


# ── Google OAuth ──────────────────────────────────────────────

import secrets
import hashlib
import base64

def _generate_pkce_pair():
    """Generate PKCE code verifier and challenge."""
    # Generate random verifier
    verifier = secrets.token_urlsafe(32)
    
    # Calculate S256 challenge
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip('=')
    
    return verifier, challenge


@auth_bp.route('/auth/google')
def google_login():
    """Redirect user to Google sign-in via Supabase OAuth (PKCE Flow)."""
    supabase = get_supabase_client()
    if not supabase:
        flash('Authentication service is not configured.', 'error')
        return redirect(url_for('auth.login'))

    # Build the callback URL
    callback_url = url_for('auth.google_callback', _external=True)
    
    # Generate PKCE verifier and challenge
    verifier, challenge = _generate_pkce_pair()
    
    # Store verifier in session for the callback
    session['oauth_verifier'] = verifier
    
    # Get redirect URL with PKCE challenge
    oauth_url = supabase.get_google_login_url(
        redirect_to=callback_url,
        code_challenge=challenge
    )

    return redirect(oauth_url)


@auth_bp.route('/auth/callback')
def google_callback():
    """Handle the redirect back from Supabase."""
    code = request.args.get('code')
    error = request.args.get('error_description') or request.args.get('error')

    if error:
        current_app.logger.warning(f"Google OAuth error: {error}")
        flash('Google sign-in failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    if not code:
        # Fallback: check if we got a fragment-based redirect (client-side implicit flow)
        # But server cannot see fragments. If code is missing here, it's a failure.
        flash('Google sign-in failed. Unknown response from provider.', 'error')
        return redirect(url_for('auth.login'))

    supabase = get_supabase_client()
    if not supabase:
        flash('Authentication service is not configured.', 'error')
        return redirect(url_for('auth.login'))
        
    # Retrieve PKCE verifier
    verifier = session.pop('oauth_verifier', None)
    if not verifier:
        flash('Session expired or invalid. Please try signing in again.', 'error')
        return redirect(url_for('auth.login'))

    try:
        # Exchange code + verifier for session
        data = supabase.exchange_code_for_session(code, code_verifier=verifier)

        user_data = data.get('user', {})
        session['user'] = {
            'id': user_data.get('id'),
            'email': user_data.get('email', ''),
            'username': user_data.get('user_metadata', {}).get('username', '') or user_data.get('user_metadata', {}).get('full_name', ''),
            'full_name': user_data.get('user_metadata', {}).get('full_name', ''),
            'avatar_url': user_data.get('user_metadata', {}).get('avatar_url', ''),
            'access_token': data.get('access_token'),
        }
        session.permanent = True

        name = session['user'].get('full_name') or session['user'].get('email', '')
        flash(f'Welcome, {name}! You are now signed in with Google.', 'success')
        return redirect(url_for('main.generate'))

    except SupabaseAuthError as e:
        current_app.logger.error(f"Google OAuth code exchange error: {e}")
        flash('Google sign-in failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    except Exception as e:
        current_app.logger.error(f"Google OAuth callback error: {e}")
        flash('Google sign-in failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))
