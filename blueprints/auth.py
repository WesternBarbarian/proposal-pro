import os
import logging
import warnings
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from functools import wraps
import requests
from oauth_config import create_oauth_flow

# Register blueprint with url_prefix to match the original routes in app.py.backup
auth_bp = Blueprint('auth', __name__, url_prefix='')

def is_user_allowed(email):
    """Check if user's email is in the allowed list or from an allowed domain."""
    from flask import current_app
    
    # Get allowed users and domains from config
    allowed_users = current_app.config.get('ALLOWED_USERS', [])
    allowed_domains = current_app.config.get('ALLOWED_DOMAINS', [])
    
    return (email in allowed_users or 
            any(email.endswith('@' + domain) for domain in allowed_domains))

def is_admin_user(email):
    """Check if a user is an admin user with session management permissions."""
    from flask import current_app
    
    # Get admin users from config
    admin_emails = current_app.config.get('ADMIN_USERS', [])
    return email in admin_emails

def require_auth(f):
    """Simplified authentication decorator that validates users once per session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if we're already authenticated
        if session.get('auth_verified'):
            # Return the function directly without any additional verification
            return f(*args, **kwargs)
        
        # Check if we have credentials
        credentials = session.get('credentials')
        if not credentials:
            # No credentials, redirect to login
            return redirect(url_for('auth.login'))
        
        # Only verify email once per session
        try:
            # Get user info from Google
            response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {credentials["token"]}'})
            
            # Check if token is valid
            if response.status_code != 200:
                session.clear()
                flash('Authentication expired. Please login again.', 'error')
                return redirect(url_for('auth.login'))
            
            # Get email and check if user is allowed
            user_info = response.json()
            email = user_info.get('email')
            
            if not email or not is_user_allowed(email):
                session.clear()
                flash('Access denied. You are not authorized.', 'error')
                return redirect(url_for('index'))
            
            # Mark as verified for the rest of the session
            session['auth_verified'] = True
            session['user_email'] = email
            session.modified = True
            
            # Continue to the original function
            return f(*args, **kwargs)
            
        except Exception as e:
            # Handle any exceptions during verification
            logging.error(f"Authentication error: {str(e)}", exc_info=True)
            session.clear()
            flash('Authentication error. Please try again.', 'error')
            return redirect(url_for('auth.login'))
            
    return decorated

# Match the original route paths from app.py.backup
@auth_bp.route('/login')
def login():
    # Clear any existing session data
    session.clear()
    
    # Create a new OAuth flow
    flow = create_oauth_flow(request.base_url)
    authorization_url, state = flow.authorization_url(
        # Enable offline access to get refresh token
        access_type='offline',
        # Force approval screen to get a refresh token every time
        prompt='consent'
    )
    
    # Store state in session and make session permanent
    session['state'] = state
    session.permanent = True
    
    # Log what we're doing
    logging.info(f"Starting login process, redirecting to: {authorization_url}")
    
    return redirect(authorization_url)

@auth_bp.route('/oauth2callback')
def oauth2callback():
    try:
        # Create a new OAuth flow
        flow = create_oauth_flow(request.base_url)
        
        # The fetch_token method can raise a Warning if scopes have changed
        # We need to catch this and continue with authentication
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Scope has changed')
            # Fetch token using authorization response
            flow.fetch_token(authorization_response=request.url)
        
        # Get credentials
        credentials = flow.credentials
        
        # Store credentials in session with consistent formatting
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Make sure session is permanent
        session.permanent = True
        session.modified = True
        
        # Reset auth_verified flag to force verification on next protected route
        session.pop('auth_verified', None)
        
        logging.info(f"OAuth callback successful, credentials stored in session")
        
        return redirect(url_for('index'))
        
    except Exception as e:
        # Log the error
        logging.error(f"OAuth callback error: {str(e)}", exc_info=True)
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for('index'))

@auth_bp.route('/logout')
def logout():
    # Clear the entire session
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for('index'))