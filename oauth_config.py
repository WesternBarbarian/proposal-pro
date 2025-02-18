
import os
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

def create_oauth_flow():
    client_config = {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.getenv("OAUTH_REDIRECT_URI")]
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES)
