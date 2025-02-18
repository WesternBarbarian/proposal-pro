
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import session

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
    
    return doc_id
