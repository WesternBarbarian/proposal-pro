
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import session
import re

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
    
    # Parse markdown and create formatting requests
    requests = []
    current_index = 1

    # Split content into paragraphs
    paragraphs = content.split('\n\n')
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        # Check for headers
        if paragraph.startswith('# '):
            text = paragraph[2:]
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text + '\n'
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(text)
                    },
                    'paragraphStyle': {
                        'namedStyleType': 'HEADING_1'
                    },
                    'fields': 'namedStyleType'
                }
            })
            current_index += len(text) + 1
        
        elif paragraph.startswith('## '):
            text = paragraph[3:]
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': text + '\n'
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(text)
                    },
                    'paragraphStyle': {
                        'namedStyleType': 'HEADING_2'
                    },
                    'fields': 'namedStyleType'
                }
            })
            current_index += len(text) + 1
            
        else:
            # Process bold and italic text
            while '**' in paragraph or '*' in paragraph:
                bold_match = re.search(r'\*\*(.*?)\*\*', paragraph)
                italic_match = re.search(r'\*(.*?)\*', paragraph)
                
                if bold_match and (not italic_match or bold_match.start() < italic_match.start()):
                    start = bold_match.start()
                    end = bold_match.end()
                    text = bold_match.group(1)
                    
                    requests.append({
                        'insertText': {
                            'location': {'index': current_index},
                            'text': text
                        }
                    })
                    requests.append({
                        'updateTextStyle': {
                            'range': {
                                'startIndex': current_index,
                                'endIndex': current_index + len(text)
                            },
                            'textStyle': {'bold': True},
                            'fields': 'bold'
                        }
                    })
                    current_index += len(text)
                    paragraph = paragraph[:start] + paragraph[end:]
                    
                elif italic_match:
                    start = italic_match.start()
                    end = italic_match.end()
                    text = italic_match.group(1)
                    
                    requests.append({
                        'insertText': {
                            'location': {'index': current_index},
                            'text': text
                        }
                    })
                    requests.append({
                        'updateTextStyle': {
                            'range': {
                                'startIndex': current_index,
                                'endIndex': current_index + len(text)
                            },
                            'textStyle': {'italic': True},
                            'fields': 'italic'
                        }
                    })
                    current_index += len(text)
                    paragraph = paragraph[:start] + paragraph[end:]
            
            # Insert remaining text
            if paragraph.strip():
                requests.append({
                    'insertText': {
                        'location': {'index': current_index},
                        'text': paragraph.strip() + '\n'
                    }
                })
                current_index += len(paragraph.strip()) + 1
    
    # Execute all formatting requests
    if requests:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
    
    return doc_id
