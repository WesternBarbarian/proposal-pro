
# Contractor Estimation Tool

A Flask-based web application that helps contractors generate professional estimates and proposals using AI. The application integrates with Google services for document management and uses Google's Generative AI for intelligent processing.

## Features

- AI-powered estimate generation from text or image inputs
- Dynamic price list management
- Professional proposal generation
- Google Drive integration for document storage
- Custom proposal template management
- Secure authentication using Google OAuth
- Automated tracking using Google Sheets

## Technical Stack

- Backend: Python/Flask
- AI: Google Generative AI
- Authentication: Google OAuth
- Storage: Google Drive, Google Docs, Google Sheets
- Frontend: Bootstrap, Custom CSS
- Session Management: Flask-Session

## Project Structure

```
├── app.py              # Main Flask application
├── ai_helper.py        # AI processing and data models
├── google_services.py  # Google API integrations
├── oauth_config.py     # OAuth configuration
├── template_manager.py # Proposal template management
├── static/            
│   └── css/           # Custom styling
├── templates/          # Flask HTML templates
└── price_list.json    # Price database
```

## Setup Requirements

1. Google Cloud Project with enabled APIs:
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - Google Generative AI API

2. Environment Variables:
   - GEMINI_API_KEY: Google Generative AI API key
   - GOOGLE_OAUTH_SECRETS: OAuth credentials JSON
   - SESSION_SECRET: Flask session secret key

## Features Breakdown

### Estimation System
- Processes project descriptions using AI
- Calculates costs based on managed price list
- Generates detailed line items

### Price Management
- Dynamic price list maintenance
- Support for different units and pricing
- Bulk price list import capability

### Proposal Generation
- AI-powered proposal writing
- Custom template support
- Direct export to Google Docs
- Professional formatting

### Document Management
- Automatic Google Drive organization
- Project tracking via Google Sheets
- Secure document storage and access

## Security

- OAuth 2.0 authentication
- Secure session management
- Role-based access control
- Environment variable configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

[Add your chosen license here]
