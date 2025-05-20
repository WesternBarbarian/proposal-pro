import os
import logging
import threading
import time


# Allow OAuth over HTTP for development (crucial for OAuth to work in dev environment)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, session, flash, redirect, url_for
from flask_session import Session
from markupsafe import Markup
import markdown2
from flask_wtf import CSRFProtect

# Import configuration
from config import get_config

# Import blueprints
from blueprints.auth import auth_bp
from blueprints.estimates import estimates_bp
from blueprints.pricing import pricing_bp
from blueprints.proposals import proposals_bp
from blueprints.prompts import prompts_bp
from blueprints.admin import admin_bp, perform_session_cleanup
from db.tenants import update_allowed_users_from_db

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

# Create Flask app
app = Flask(__name__)


# Load configuration from config.py
app.config.from_object(get_config())

# Create the session directory if it doesn't exist
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Set logger level from config
app.logger.setLevel(logging.DEBUG if app.config['DEBUG'] else logging.INFO)

# Set CSRF key same as secret key if not otherwise specified
if 'WTF_CSRF_SECRET_KEY' not in app.config:
    app.config['WTF_CSRF_SECRET_KEY'] = app.config['SECRET_KEY']

# Initialize Session
Session(app)

# Initialize Markdown
markdown = markdown2.Markdown()

# Register markdown filter with None handling
app.jinja_env.filters['markdown'] = lambda text: Markup(markdown.convert(text)) if text else Markup('')

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Import database modules
from db.connection import init_app as init_db
from db.commands import register_commands as register_db_commands

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(estimates_bp)
app.register_blueprint(pricing_bp)
app.register_blueprint(proposals_bp)
app.register_blueprint(prompts_bp)
app.register_blueprint(admin_bp)

# Initialize database
init_db(app)

# Initialize price lists within app context
with app.app_context():
    from db.price_lists import initialize_price_lists
    initialize_price_lists()

register_db_commands(app)

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
    # Use the existing app that's already configured
    # with all blueprints and middleware
    app.run(host='0.0.0.0', port=5000, debug=True)