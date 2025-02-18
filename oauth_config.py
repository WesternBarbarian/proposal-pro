
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
        base_url = "https://e0195ec9-bbd4-4786-9209-a61c7380599c-00-3u1qtz4pwrw1h.riker.replit.dev"
        flow.redirect_uri = f"{base_url}/oauth2callback"
    return flow
