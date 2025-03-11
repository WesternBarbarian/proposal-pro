import os
import json
import logging
from datetime import datetime, timedelta
import requests
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allow OAuth over HTTP for development
from flask import Flask, render_template, request, flash, redirect, url_for, make_response, session
from oauth_config import create_oauth_flow
from google_services import create_folder_if_not_exists, create_doc_in_folder, create_tracking_sheet_if_not_exists, append_to_sheet, get_sheets_service
from markupsafe import Markup
from flask_session import Session
import markdown2
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
from ai_helper import (
    extract_project_data, 
    extract_project_data_from_image, 
    generate_proposal, 
    generate_price_list,
    generate_price_list_from_image,
    lookup_prices, 
    Line_Items, 
    Line_Item
)
from template_manager import load_templates, add_template, delete_template

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)

app.logger.setLevel(logging.DEBUG)
# Configure session to use filesystem (Replit resets in-memory sessions)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True  # Make sessions persistent
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Sessions last for 1 day
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'flask_'
app.config['SECRET_KEY'] = os.environ.get("SESSION_SECRET", "fallback_secret_key_for_development")
app.config['WTF_CSRF_SECRET_KEY'] = app.config['SECRET_KEY']

# Initialize Session
Session(app)

# Initialize Markdown
markdown = markdown2.Markdown()

# Register markdown filter
app.jinja_env.filters['markdown'] = lambda text: Markup(markdown.convert(text))


csrf = CSRFProtect()
csrf.init_app(app)

from flask_wtf.file import FileField, FileAllowed
class ProjectForm(FlaskForm):
    project_description = TextAreaField('Project Description')
    file = FileField('Upload File', validators=[
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'heic'], 'Only PDF, PNG, JPEG, and HEIC files allowed!')
    ])
    submit = SubmitField('Generate Estimate')

class PriceListForm(FlaskForm):
    price_description = TextAreaField('Price Description')
    file = FileField('Upload File', validators=[
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'heic'], 'Only PDF, PNG, JPEG, and HEIC files allowed!')
    ])
    submit = SubmitField('Generate Price List')

# Load price list
def load_price_list():
    try:
        with open('price_list.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save price list
def save_price_list(price_list):
    if hasattr(price_list, 'prices'):
        # Convert Items object to dictionary
        price_dict = {item.item: {"unit": item.unit, "price": item.price} for item in price_list.prices}
    else:
        price_dict = price_list

    with open('price_list.json', 'w') as f:
        json.dump(price_dict, f, indent=4)

ALLOWED_USERS = ['jason.matthews@cyborguprising.com']  # Replace with allowed emails
ALLOWED_DOMAINS = ['cyborguprising.com']  # Replace with allowed domains

def is_user_allowed(email):
    return (email in ALLOWED_USERS or 
            any(email.endswith('@' + domain) for domain in ALLOWED_DOMAINS))

def require_auth(f):
    """Simplified authentication decorator that validates users once per session.
    
    Instead of making API calls on every request, it only validates a user once
    when they first log in, then stores the verification in the session.
    """
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if we're already authenticated
        if session.get('auth_verified'):
            # Return the function directly without any additional verification
            return f(*args, **kwargs)
        
        # Check if we have credentials
        credentials = session.get('credentials')
        if not credentials:
            # No credentials, redirect to login
            return redirect(url_for('login'))
        
        # Only verify email once per session
        try:
            # Get user info from Google
            response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {credentials["token"]}'})
            
            # Check if token is valid
            if response.status_code != 200:
                session.clear()
                flash('Authentication expired. Please login again.', 'error')
                return redirect(url_for('login'))
            
            # Get email and check if user is allowed
            user_info = response.json()
            email = user_info.get('email')
            
            if not email or not is_user_allowed(email):
                session.clear()
                flash('Access denied. You are not authorized.', 'error')
                return redirect(url_for('index'))
            
            # Mark as verified for the rest of the session
            session['auth_verified'] = True
            session['user_email'] = email
            session.modified = True
            
            # Continue to the original function
            return f(*args, **kwargs)
            
        except Exception as e:
            # Handle any exceptions during verification
            app.logger.error(f"Authentication error: {str(e)}", exc_info=True)
            session.clear()
            flash('Authentication error. Please try again.', 'error')
            return redirect(url_for('login'))
            
    return decorated

@app.route('/')
def index():
    # Simplified index route to prevent multiple API calls
    authenticated = False
    credentials = session.get('credentials')
    if credentials:
        # Just check if credentials exist, don't make API calls on every page load
        authenticated = True
    return render_template('index.html', authenticated=authenticated)

@app.route('/login')
def login():
    # Clear any existing session data
    session.clear()
    
    # Create a new OAuth flow
    flow = create_oauth_flow(request.base_url)
    authorization_url, state = flow.authorization_url(
        # Enable offline access to get refresh token
        access_type='offline',
        # Force approval screen to get a refresh token every time
        prompt='consent'
    )
    
    # Store state in session and make session permanent
    session['state'] = state
    session.permanent = True
    
    # Log what we're doing
    app.logger.info(f"Starting login process, redirecting to: {authorization_url}")
    
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    try:
        # Create a new OAuth flow
        flow = create_oauth_flow(request.base_url)
        
        # Fetch token using authorization response
        flow.fetch_token(authorization_response=request.url)
        
        # Get credentials
        credentials = flow.credentials
        
        # Store credentials in session
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # Make sure session is permanent
        session.permanent = True
        session.modified = True
        
        # Reset auth_verified flag to force verification on next protected route
        session.pop('auth_verified', None)
        
        app.logger.info(f"OAuth callback successful, credentials stored in session")
        
        return redirect('/')
        
    except Exception as e:
        # Log the error
        app.logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        flash("Authentication failed. Please try again.", "error")
        return redirect('/')

@app.route('/logout')
def logout():
    # Clear the entire session
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect('/')


@app.route('/estimate', methods=['GET'])
@require_auth
def estimate():
    form = ProjectForm()
    return render_template('estimate.html', form=form, authenticated=True)

@app.route('/process_estimate', methods=['POST'])
@require_auth
def process_estimate():
    try:
        # Simple extraction from form data
        if request.files.get('file') and request.files['file'].filename:
            # Handle file upload
            file = request.files['file']
            temp_path = f"temp_{file.filename}"
            file.save(temp_path)
            try:
                customer, project_details = extract_project_data_from_image(temp_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        elif request.form.get('project_description'):
            # Handle text input
            project_data = request.form.get('project_description')
            customer, project_details = extract_project_data(project_data)
        else:
            flash('Please provide either a file or project description.', 'error')
            return redirect(url_for('estimate'))

        # Validate extracted data
        if not customer or not project_details:
            flash('Failed to extract project details. Please try again.', 'error')
            return redirect(url_for('estimate'))

        # Price calculation
        price_list = load_price_list()
        line_items = lookup_prices(project_details, price_list)
        total_cost = line_items.sub_total
        line_items_dict = line_items.dict()

        # Store data in global variable AND session
        estimate_result = {
            'project_details': project_details,
            'customer': customer,
            'line_items': line_items_dict,
            'total_cost': total_cost
        }
        
        # Use both session and global variable
        app.config['CURRENT_ESTIMATE'] = estimate_result
        session['estimate_data'] = estimate_result
        session.modified = True
        
        # Make session permanent to avoid timeout
        session.permanent = True
        
        # Debug log the session state
        app.logger.debug(f"Session data set: {session.get('estimate_data')}")
        app.logger.debug(f"App config: {app.config.get('CURRENT_ESTIMATE') is not None}")
        
        # Redirect to results
        return redirect(url_for('estimate_results'))
        
    except Exception as e:
        error_msg = str(e)
        app.logger.error(f"Error processing estimate: {error_msg}", exc_info=True)
        flash(f'Error processing request: {error_msg}', 'error')
        return redirect(url_for('estimate'))

@app.route('/estimate_results')
@require_auth
def estimate_results():
    # Try to get data from session first
    estimate_data = session.get('estimate_data')
    
    # If not in session, try to get from app config
    if not estimate_data:
        estimate_data = app.config.get('CURRENT_ESTIMATE')
        
    # If still no data, redirect
    if not estimate_data:
        flash('No estimate data found. Please create a new estimate.', 'error')
        return redirect(url_for('estimate'))
    
    # Log what we found
    app.logger.debug(f"Using estimate data: {estimate_data}")
    
    # Render template with data
    return render_template('estimate_results.html',
                          project_details=estimate_data['project_details'],
                          total_cost=estimate_data['total_cost'],
                          customer=estimate_data['customer'],
                          line_items=estimate_data['line_items'],
                          authenticated=True)

@app.route('/generate_proposal', methods=['POST'])
@require_auth
def create_proposal():
    try:
        # Get data from form
        project_details = json.loads(request.form.get('project_details', '{}'))
        line_items_data = json.loads(request.form.get('line_items', '{"lines":[]}'))
        customer_data = json.loads(request.form.get('customer', '{}'))
        
        # Validate data
        if not project_details or not line_items_data or not customer_data:
            # Try to get data from session
            estimate_data = session.get('estimate_data')
            if estimate_data:
                project_details = estimate_data.get('project_details', {})
                customer_data = estimate_data.get('customer', {})
                line_items_data = estimate_data.get('line_items', {'lines': []})
            
            # If still no data, try app config
            if not project_details or not line_items_data or not customer_data:
                estimate_data = app.config.get('CURRENT_ESTIMATE')
                if estimate_data:
                    project_details = estimate_data.get('project_details', {})
                    customer_data = estimate_data.get('customer', {})
                    line_items_data = estimate_data.get('line_items', {'lines': []})
        
        # If we still don't have data, redirect back
        if not project_details or not line_items_data or not customer_data:
            flash('No project data found. Please create an estimate first.', 'error')
            return redirect(url_for('estimate'))
            
        # Convert line items to proper object
        lines = line_items_data.get('lines', [])
        line_items = Line_Items(lines=[
            Line_Item(
                name=item.get('name', 'Unknown'),
                unit=item.get('unit', 'ea'),
                price=float(item.get('price', 0)),
                quantity=int(item.get('quantity', 0))
            ) for item in lines
        ])
        
        # Get templates
        templates, _ = load_templates()
        if isinstance(templates, list):
            templates = [str(t) for t in templates]
        else:
            templates = [str(templates)]
            
        # Generate proposal
        proposal = generate_proposal(project_details, customer_data, line_items, templates)
        
        # Keep data in session for next steps
        app.config['CURRENT_PROPOSAL'] = {
            'proposal': proposal,
            'customer': customer_data
        }
        
        session['proposal_data'] = {
            'proposal': proposal,
            'customer': customer_data
        }
        session.modified = True
        
        return render_template('proposal.html', 
                            proposal=proposal,
                            raw_proposal=proposal,  # For markdown editing
                            customer=customer_data,
                            authenticated=True)
    except Exception as e:
        logging.error(f"Error generating proposal: {str(e)}", exc_info=True)
        flash(f'Error generating proposal: {str(e)}. Please try again.', 'error')
        return redirect(url_for('estimate'))

@app.route('/save_proposal', methods=['POST'])
@require_auth
def save_proposal():
    try:
        edited_proposal = request.form.get('edited_proposal')
        response = make_response(edited_proposal)
        response.headers['Content-Type'] = 'text/markdown'
        response.headers['Content-Disposition'] = 'attachment; filename=proposal.md'
        return response
    except Exception as e:
        logging.error(f"Error saving proposal: {str(e)}")
        flash('Error saving proposal. Please try again.', 'error')
        return redirect(url_for('estimate'))

@app.route('/save-to-drive', methods=['POST'])
@require_auth
def save_to_drive():

    try:
        content = request.form.get('proposal_content')


        folder_id = create_folder_if_not_exists('proposal-pro')

        if not folder_id:
            flash('Please log in to save to Google Drive.', 'error')
            return redirect(url_for('login'))

        content = request.form.get('proposal_content')

        # Update the last row of tracking sheet with proposal content
        try:
            sheet_id = create_tracking_sheet_if_not_exists(folder_id)
            if sheet_id:
                sheets_service = get_sheets_service()
                result = sheets_service.spreadsheets().values().get(
                    spreadsheetId=sheet_id,
                    range='A:A'
                ).execute()
                last_row = len(result.get('values', [])) + 1
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id,
                    range='C' + str(sheets_service.spreadsheets().values().get(
                        spreadsheetId=sheet_id,
                        range='A:A'
                    ).execute().get('values', []).__len__()),
                    valueInputOption='RAW',
                    body={'values': [[content]]}
                ).execute()
        except Exception as e:
            app.logger.error(f"Error updating tracking sheet with proposal: {str(e)}")

        # Get customer name from form
        safe_name = request.form.get('customer_name', 'Unknown Customer')

        doc_id = create_doc_in_folder(
            f"Proposal - {safe_name} - {datetime.now().strftime('%Y-%m-%d')}",
            content,
            folder_id
        )

        app.logger.info(f"Created document for customer: {safe_name}")

        flash('Proposal saved to Google Drive successfully!', 'success')
        return redirect(url_for('estimate'))
    except Exception as e:
        logging.error(f"Error saving to Google Drive: {str(e)}")
        flash('Error saving to Google Drive. Please try again.', 'error')
        return redirect(url_for('estimate'))

@app.route('/price-list', methods=['GET', 'POST'])
@require_auth
def price_list():
    form = PriceListForm()
    current_prices = load_price_list()
    return render_template('price_list.html', 
                          form=form, 
                          current_prices=current_prices,
                          authenticated=True)



@app.route('/generate-price-list', methods=['POST'])
@require_auth
def generate_price_list_route():
    form = PriceListForm()
    if form.validate_on_submit():
        try:
            app.logger.info("Form validation successful")
            price_data = ""

            if form.file.data:
                file = form.file.data
                # Save file temporarily
                temp_path = f"temp_{file.filename}"
                file.save(temp_path)
                try:
                    items = generate_price_list_from_image(temp_path)
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            elif form.price_description.data:
                items = generate_price_list(form.price_description.data)
            else:
                flash('Please provide either a file or price description.', 'error')
                return redirect(url_for('price_list'))

            app.logger.info(f"Generated Items: {items}")
            save_price_list(items)
            app.logger.info("Price list saved successfully")
            flash('Price list updated successfully!', 'success')
            return redirect(url_for('price_list'))
        except Exception as e:
            app.logger.error(f"Error generating price list: {str(e)}", exc_info=True)
            flash('Error generating price list. Please try again.', 'error')
    else:
        app.logger.error(f"Form validation failed. Errors: {form.errors}")
        flash('Invalid form submission.', 'error')

    return redirect(url_for('price_list'))

@app.route('/delete-price', methods=['POST'])
@require_auth
def delete_price():
    try:
        item = request.form.get('item')
        if not item:
            flash('Invalid delete request.', 'error')
            return redirect(url_for('price_list'))

        # Load current price list
        price_list = load_price_list()

        # Delete item
        if item in price_list:
            del price_list[item]
            save_price_list(price_list)
            flash('Item deleted successfully!', 'success')
        else:
            flash('Item not found.', 'error')
    except Exception as e:
        logging.error(f"Error deleting price: {str(e)}")
        flash('Error deleting price. Please try again.', 'error')

    return redirect(url_for('price_list'))

@app.route('/add-price', methods=['POST'])
@require_auth
def add_price():
    try:
        item = request.form.get('item')
        price = float(request.form.get('price'))
        unit = request.form.get('unit')

        if not item or price < 0 or not unit:
            flash('Invalid price addition request.', 'error')
            return redirect(url_for('price_list'))

        # Load current price list
        price_list = load_price_list()

        # Check if item already exists
        if item in price_list:
            flash('Item already exists.', 'error')
            return redirect(url_for('price_list'))

        # Add new item
        price_list[item] = {
            "unit": unit,
            "price": price
        }

        # Save updated price list
        save_price_list(price_list)

        flash('Item added successfully!', 'success')
    except Exception as e:
        logging.error(f"Error adding price: {str(e)}")
        flash('Error adding price. Please try again.', 'error')

    return redirect(url_for('price_list'))

@app.route('/update-price', methods=['POST'])
@require_auth
def update_price():
    try:
        item = request.form.get('item')
        price = float(request.form.get('price'))
        unit = request.form.get('unit')

        if not item or price < 0 or not unit:
            flash('Invalid price update request.', 'error')
            return redirect(url_for('price_list'))

        # Load current price list
        price_list = load_price_list()

        # Update price and unit
        price_list[item] = {
            "unit": unit,
            "price": price
        }

        # Save updated price list
        save_price_list(price_list)
        flash('Price updated successfully!', 'success')
    except Exception as e:
        logging.error(f"Error updating price: {str(e)}")
        flash('Error updating price. Please try again.', 'error')
    return redirect(url_for('price_list'))

@app.route('/proposal-templates', methods=['GET'])
@require_auth
def proposal_templates():
    templates, using_custom = load_templates()
    # We're already authenticated by the @require_auth decorator
    authenticated = True
    return render_template('proposal_templates.html', 
                         templates=templates, 
                         using_custom=using_custom,
                         authenticated=authenticated)

@app.route('/add-template', methods=['POST'])
@require_auth
def add_template_route():
    template_text = request.form.get('template')
    success, message = add_template(template_text)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('proposal_templates'))

@app.route('/delete-template', methods=['POST'])
@require_auth
def delete_template_route():
    template_id = int(request.form.get('template_id'))
    success, message = delete_template(template_id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('proposal_templates'))

#if __name__ == '__main__':
 #   app.run(host='0.0.0.0', port=5000, debug=True)