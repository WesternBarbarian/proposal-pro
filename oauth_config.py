
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

def create_oauth_flow():
    client_secrets = json.loads(os.getenv("GOOGLE_OAUTH_SECRETS"))
    return Flow.from_client_config(client_secrets, scopes=SCOPES)
