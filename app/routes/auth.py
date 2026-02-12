"""
Auth routes for Prosno.io (Public User Authentication via Supabase REST API)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from app import csrf, limiter
from app.utils.supabase_auth import SupabaseAuthError

auth_bp = Blueprint('auth', __name__)


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
                'access_token': data.get('access_token'),
            }
            session.permanent = True

            flash('Welcome back! You are now logged in.', 'success')

            # Redirect to next page or generate
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('main.generate'))

        except SupabaseAuthError as e:
            error_msg = str(e)
            if 'Invalid login credentials' in error_msg:
                flash('Invalid email or password.', 'error')
            elif 'Email not confirmed' in error_msg:
                flash('Please confirm your email before logging in. Check your inbox.', 'warning')
            else:
                flash('Login failed. Please try again.', 'error')
                current_app.logger.error(f"Supabase login error: {error_msg}")
        except Exception as e:
            flash('Login failed. Please try again.', 'error')
            current_app.logger.error(f"Login error: {e}")

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

        # Validation
        if not email or not password:
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
            data = supabase.sign_up(email, password)

            user_data = data.get('user', {})
            identities = user_data.get('identities', [])

            if user_data and identities:
                # Check if session was returned (auto-confirm enabled)
                if data.get('access_token'):
                    session['user'] = {
                        'id': user_data.get('id'),
                        'email': user_data.get('email', email),
                        'access_token': data.get('access_token'),
                    }
                    session.permanent = True
                    flash('Account created successfully! Welcome!', 'success')
                    return redirect(url_for('main.generate'))
                else:
                    flash('Account created! Please check your email to confirm, then log in.', 'success')
                    return redirect(url_for('auth.login'))
            elif user_data and not identities:
                # User already exists (Supabase returns empty identities for duplicates)
                flash('An account with this email already exists. Please log in.', 'error')
            else:
                flash('Registration failed. Please try again.', 'error')

        except SupabaseAuthError as e:
            error_msg = str(e)
            if 'already registered' in error_msg.lower():
                flash('An account with this email already exists. Please log in.', 'error')
            elif 'password' in error_msg.lower():
                flash('Password is too weak. Use at least 6 characters.', 'error')
            else:
                flash('Registration failed. Please try again.', 'error')
                current_app.logger.error(f"Supabase registration error: {error_msg}")
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
            current_app.logger.error(f"Registration error: {e}")

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


@auth_bp.route('/auth/google')
def google_login():
    """Redirect user to Google sign-in via Supabase OAuth."""
    supabase = get_supabase_client()
    if not supabase:
        flash('Authentication service is not configured.', 'error')
        return redirect(url_for('auth.login'))

    # Build the callback URL that Supabase will redirect to after Google consent
    callback_url = url_for('auth.google_callback', _external=True)
    oauth_url = supabase.get_google_login_url(redirect_to=callback_url)

    return redirect(oauth_url)


@auth_bp.route('/auth/callback')
def google_callback():
    """Handle the redirect back from Supabase after Google OAuth consent."""
    code = request.args.get('code')

    if not code:
        # Check for error from Supabase
        error = request.args.get('error_description') or request.args.get('error')
        flash(f'Google sign-in failed: {error or "No authorization code received."}', 'error')
        return redirect(url_for('auth.login'))

    supabase = get_supabase_client()
    if not supabase:
        flash('Authentication service is not configured.', 'error')
        return redirect(url_for('auth.login'))

    try:
        data = supabase.exchange_code_for_session(code)

        user_data = data.get('user', {})
        session['user'] = {
            'id': user_data.get('id'),
            'email': user_data.get('email', ''),
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
