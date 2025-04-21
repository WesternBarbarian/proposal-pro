import os
import logging
import threading
import time
import glob
from datetime import timedelta

# Allow OAuth over HTTP for development (crucial for OAuth to work in dev environment)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, session, flash, redirect, url_for
from flask_session import Session
from markupsafe import Markup
import markdown2
from flask_wtf import CSRFProtect

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.estimates import estimates_bp
from blueprints.pricing import pricing_bp
from blueprints.proposals import proposals_bp
from blueprints.admin import admin_bp, SESSION_DIR, MAX_SESSION_FILES, perform_session_cleanup

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# How often to clean up (in seconds)
CLEANUP_INTERVAL = 3600  # 1 hour

def cleanup_session_files():
    """Clean up old session files periodically to prevent directory bloat."""
    while True:
        try:
            # Sleep first to allow the app to start properly
            time.sleep(CLEANUP_INTERVAL)
            
            # Run the cleanup
            deleted = perform_session_cleanup()
            if deleted > 0:
                logging.info(f"Background cleanup removed {deleted} old session files")
                
        except Exception as e:
            logging.error(f"Error in session cleanup thread: {str(e)}")

# Create the session directory if it doesn't exist
os.makedirs(SESSION_DIR, exist_ok=True)

# Create Flask app
app = Flask(__name__)

app.logger.setLevel(logging.DEBUG)
# Configure session to use filesystem (Replit resets in-memory sessions)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True  # Make sessions persistent
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Sessions last for 1 day
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'flask_'
app.config['SESSION_FILE_DIR'] = SESSION_DIR  # Specify the session directory
app.config['SECRET_KEY'] = os.environ.get("SESSION_SECRET", "fallback_secret_key_for_development")
app.config['WTF_CSRF_SECRET_KEY'] = app.config['SECRET_KEY']

# Initialize Session
Session(app)

# Initialize Markdown
markdown = markdown2.Markdown()

# Register markdown filter
app.jinja_env.filters['markdown'] = lambda text: Markup(markdown.convert(text))

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(estimates_bp)
app.register_blueprint(pricing_bp)
app.register_blueprint(proposals_bp)
app.register_blueprint(admin_bp)

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_session_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def index():
    # Simplified index route to prevent multiple API calls
    authenticated = False
    credentials = session.get('credentials')
    if credentials:
        # Just check if credentials exist, don't make API calls on every page load
        authenticated = True
    return render_template('index.html', authenticated=authenticated)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)