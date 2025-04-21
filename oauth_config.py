
import os
import json
from flask import current_app
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

def create_oauth_flow(request_url=None):
    """Create and configure an OAuth flow for Google authentication.
    
    Args:
        request_url: The URL of the current request, used to determine the redirect URI.
        
    Returns:
        A configured Flow object for OAuth authentication.
    """
    # Get client credentials from GOOGLE_OAUTH_SECRETS environment variable
    oauth_secrets = os.getenv("GOOGLE_OAUTH_SECRETS")
    if not oauth_secrets:
        raise ValueError("GOOGLE_OAUTH_SECRETS environment variable is not set")
    client_secrets = json.loads(oauth_secrets)
    
    # Get scopes from app config
    scopes = current_app.config.get('GOOGLE_API_SCOPES', [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/drive.file',
        'openid'
    ])
    
    # Create the OAuth flow
    flow = Flow.from_client_config(client_secrets, scopes=scopes)
    
    if request_url:
        # Get the base URL from the request and ensure HTTPS
        if "://" in request_url:
            # Extract base URL from the full URL (remove path components)
            parts = request_url.split("/")
            base_url = "/".join(parts[:3])  # Keep scheme + hostname + port
            # Ensure HTTPS is used (Google requires HTTPS for OAuth)
            base_url = base_url.replace("http://", "https://")
        else:
            # Fallback to a known URL format
            base_url = f"https://{os.environ.get('REPL_SLUG', 'app')}.{os.environ.get('REPL_OWNER', 'repl')}.repl.co"
        
        # Set the redirect URI
        flow.redirect_uri = f"{base_url}/oauth2callback"
        
    return flow
