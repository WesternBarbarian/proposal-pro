
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',  # For file/folder operations
    'https://www.googleapis.com/auth/spreadsheets',  # For Google Sheets
    'https://www.googleapis.com/auth/documents',  # For Google Docs
    'https://www.googleapis.com/auth/userinfo.profile',  # Basic user info
    'https://www.googleapis.com/auth/userinfo.email',  # User email
    'openid'  # OpenID Connect
]

def create_oauth_flow(request_url=None):
    client_secrets = json.loads(os.getenv("GOOGLE_OAUTH_SECRETS"))
    flow = Flow.from_client_config(client_secrets, scopes=SCOPES)
    if request_url:
        # Get the base URL from the request
        if "://" in request_url:
            # Extract base URL from the full URL (remove path components)
            parts = request_url.split("/")
            base_url = "/".join(parts[:3])  # Keep scheme + hostname + port
        else:
            # Fallback to a known URL format
            base_url = f"https://{os.environ.get('REPL_SLUG', 'app')}.{os.environ.get('REPL_OWNER', 'repl')}.repl.co"
        flow.redirect_uri = f"{base_url}/oauth2callback"
    return flow
