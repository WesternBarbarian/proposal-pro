
import time
import random
import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from flask import session

logger = logging.getLogger(__name__)

def retry_with_backoff(max_retries=3, base_delay=1, max_delay=60):
    """Decorator to add retry logic with exponential backoff for Google API calls"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except HttpError as e:
                    # Check if it's a rate limit error (429) or server error (5xx)
                    if e.resp.status in [429, 500, 502, 503, 504]:
                        if attempt < max_retries:
                            # Calculate delay with exponential backoff and jitter
                            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                            logger.warning(f"API call failed with status {e.resp.status}, retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})")
                            time.sleep(delay)
                            continue
                    # Re-raise the error if it's not retryable or max retries exceeded
                    raise
                except Exception as e:
                    # For non-HTTP errors, don't retry
                    raise
            return None
        return wrapper
    return decorator

def get_service(service_name, version):
    if 'credentials' not in session:
        return None
        
    credentials = Credentials(**session['credentials'])
    return build(service_name, version, credentials=credentials)

def get_drive_service():
    return get_service('drive', 'v3')

def get_docs_service():
    return get_service('docs', 'v1')

def get_sheets_service():
    return get_service('sheets', 'v4')

@retry_with_backoff(max_retries=3)
def create_tracking_sheet_if_not_exists(folder_id):
    drive_service = get_drive_service()
    sheets_service = get_sheets_service()
    
    if not drive_service or not sheets_service:
        return None
        
    # Search for existing sheet
    query = f"name='tracking' and mimeType='application/vnd.google-apps.spreadsheet' and '{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive').execute()
    items = results.get('files', [])
    
    if items:
        return items[0]['id']
    
    # Create new sheet
    sheet_metadata = {
        'properties': {'title': 'tracking'}
    }
    
    spreadsheet = sheets_service.spreadsheets().create(
        body=sheet_metadata,
        fields='spreadsheetId'
    ).execute()
    
    # Move file to correct folder
    drive_service.files().update(
        fileId=spreadsheet['spreadsheetId'],
        addParents=folder_id,
        fields='id, parents'
    ).execute()
    
    # Write header
    sheet_values = [['Form Data', 'Line Items', 'Proposal']]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet['spreadsheetId'],
        range='A1',
        valueInputOption='RAW',
        body={'values': sheet_values}
    ).execute()
    
    return spreadsheet['spreadsheetId']

@retry_with_backoff(max_retries=3)
def append_to_sheet(spreadsheet_id, values):
    sheets_service = get_sheets_service()
    if not sheets_service:
        return None
        
    body = {
        'values': values
    }
    
    result = sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range='A:A',
        valueInputOption='RAW',
        body=body
    ).execute()
    
    return result

@retry_with_backoff(max_retries=3)
def create_folder_if_not_exists(folder_name):
    drive_service = get_drive_service()
    if not drive_service:
        return None

    # Search for existing folder
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive_service.files().list(q=query, spaces='drive').execute()
    items = results.get('files', [])

    if items:
        return items[0]['id']
    
    # Create folder if it doesn't exist
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')

@retry_with_backoff(max_retries=3)
def create_doc_in_folder(title, content, folder_id):
    drive_service = get_drive_service()
    docs_service = get_docs_service()
    
    # Create empty doc
    doc_metadata = {
        'name': title,
        'parents': [folder_id],
        'mimeType': 'application/vnd.google-apps.document'
    }
    doc = drive_service.files().create(body=doc_metadata, fields='id').execute()
    doc_id = doc.get('id')
    
    # Insert content
    requests = [
        {
            'insertText': {
                'location': {
                    'index': 1
                },
                'text': content
            }
        }
    ]
    
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': requests}
    ).execute()
    
    # Return document info as dictionary
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    return {
        'id': doc_id,
        'doc_url': doc_url
    }
