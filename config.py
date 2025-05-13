import os
from datetime import timedelta

class BaseConfig:
    """Base configuration settings for the application."""
    # Secret key for session and CSRF protection
    SECRET_KEY = os.environ.get("SESSION_SECRET", "dev-secret-key")
    
    # Flask session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    SESSION_TYPE = "filesystem"
    SESSION_FILE_DIR = "flask_session"
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_FILE_THRESHOLD = 100
    
    # Session cleanup settings
    MAX_SESSION_FILES = 20
    SESSION_CLEANUP_THRESHOLD = 86400  # 24 hours in seconds
    
    # Authentication settings - default values
    ALLOWED_USERS = ['jason.matthews@cyborguprising.com']  # Will be updated from DB
    ALLOWED_DOMAINS = ['cyborguprising.com']
    ADMIN_USERS = ['jason.matthews@cyborguprising.com']
    
    def update_allowed_users_from_db(self):
        """Update ALLOWED_USERS from database tenants"""
        try:
            from db.tenants import get_allowed_tenants
            from flask import current_app
            
            # Get Flask app context if available, otherwise continue with defaults
            tenant_emails = get_allowed_tenants()
            
            if tenant_emails:
                # Keep original admin users in the allowed list
                self.ALLOWED_USERS = list(set(tenant_emails + self.ADMIN_USERS))
                
                if hasattr(current_app, 'logger') and current_app.logger:
                    current_app.logger.info(f"Updated ALLOWED_USERS from database: {len(self.ALLOWED_USERS)} users")
        except Exception as e:
            import logging
            logging.error(f"Failed to update allowed users from database: {e}")
            # Keep using default ALLOWED_USERS
    
    def update_allowed_domains_from_db(self):
        """Update ALLOWED_DOMAINS from database tenants based on plan level"""
        try:
            from db.tenants import get_allowed_domains
            from flask import current_app
            
            # Get domains from tenants with super/basic plan
            tenant_domains = get_allowed_domains()
            
            if tenant_domains:
                # Add to default domains without duplicates
                self.ALLOWED_DOMAINS = list(set(tenant_domains + self.ALLOWED_DOMAINS))
                
                if hasattr(current_app, 'logger') and current_app.logger:
                    current_app.logger.info(f"Updated ALLOWED_DOMAINS from database: {len(self.ALLOWED_DOMAINS)} domains")
        except Exception as e:
            import logging
            logging.error(f"Failed to update allowed domains from database: {e}")
            # Keep using default ALLOWED_DOMAINS
    
    # Google OAuth settings
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    
    # Google API settings
    GOOGLE_API_SCOPES = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/drive.file',
        'openid'
    ]
    
    # File path settings
    PRICE_LIST_FILE = "price_list.json"
    TEMPLATES_FILE = "default_template.json"
    
    # Debug mode
    DEBUG = True

class DevelopmentConfig(BaseConfig):
    """Development configuration settings."""
    pass

class ProductionConfig(BaseConfig):
    """Production configuration settings."""
    DEBUG = False
    # In production, always use environment variables for secrets
    SECRET_KEY = os.environ.get("SESSION_SECRET")
    
    # Session security settings for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True

def get_config():
    """Return the appropriate configuration object based on the environment."""
    env = os.environ.get("FLASK_ENV", "development")
    
    if env == "production":
        return ProductionConfig()
    else:
        return DevelopmentConfig()