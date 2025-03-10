import os
import json
import logging
from datetime import datetime
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
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'flask_'
app.config['SECRET_KEY'] = os.environ.get("SESSION_SECRET", "fallback_secret")
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
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        credentials = session.get('credentials')
        if not credentials:
            return redirect(url_for('login'))
        try:
            response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {credentials["token"]}'})
            if response.status_code == 401:
                session.clear()
                return redirect(url_for('login'))
            user_info = response.json()
            email = user_info.get('email')
            if not email or not is_user_allowed(email):
                session.clear()
                flash('Access denied. You are not authorized.', 'error')
                return redirect(url_for('index'))
        except Exception as e:
            app.logger.error(f"Auth error: {str(e)}")
            session.clear()
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    app.logger.info("Home route was accessed")
    credentials = session.get('credentials')
    if credentials:
        try:
            response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {credentials["token"]}'})
            if response.status_code == 401:
                # Token expired or invalid
                session.clear()
                return render_template('index.html', authenticated=False)

            user_info = response.json()
            email = user_info.get('email')
            if email and is_user_allowed(email):
                return render_template('index.html', authenticated=True)
            session.clear()
            return "Access Denied", 403
        except Exception as e:
            app.logger.error(f"Auth error: {str(e)}")
            session.clear()
            return render_template('index.html', authenticated=False)
    return render_template('index.html', authenticated=False)

@app.route('/login')
def login():
    flow = create_oauth_flow(request.base_url)
    authorization_url, state = flow.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    flow = create_oauth_flow(request.base_url)
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('credentials', None)
    return redirect('/')


@app.route('/estimate', methods=['GET', 'POST'])
@require_auth
def estimate():
    form = ProjectForm()
    if form.validate_on_submit():
        try:
            file_info = "No file uploaded"
            project_data = ""

            if form.file.data:
                file = form.file.data
                file_info = f"File upload: {file.filename}"
                app.logger.info(f"Processing uploaded file: {file.filename}")
                # Save file temporarily
                temp_path = f"temp_{file.filename}"
                file.save(temp_path)
                try:
                    app.logger.info(f"Extracting data from image at {temp_path}")
                    customer, project_details = extract_project_data_from_image(temp_path)
                    app.logger.info(f"Customer data extracted: {customer}")
                    app.logger.info(f"Project details extracted: {project_details}")
                    # Set project_data for consistency with text input flow
                    project_data = f"Data extracted from image: {file.filename}"
                except Exception as e:
                    app.logger.error(f"Error extracting data from image: {str(e)}")
                    raise
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                        app.logger.info(f"Temporary file {temp_path} removed")
            elif form.project_description.data:
                project_data = form.project_description.data
                if not project_data:
                    flash('Please provide either a file or project description.', 'error')
                    return redirect(url_for('estimate'))
                customer, project_details = extract_project_data(project_data)
            app.logger.debug(f"Project details returned from analyze_project: {project_details}")
            price_list = load_price_list()

            # Track form data in Google Sheet if user is authenticated
            if 'credentials' in session:
                try:
                    folder_id = create_folder_if_not_exists('proposal-pro')
                    # Get line items with prices
                    line_items = lookup_prices(project_details, price_list)
                    app.logger.debug(f"Line items after lookup_prices: {line_items}")

                    if folder_id:
                        sheet_id = create_tracking_sheet_if_not_exists(folder_id)
                        if sheet_id:
                            # Use project_data for both file uploads and text input
                            values = [[project_data, json.dumps(line_items.dict()), file_info]]
                            append_to_sheet(sheet_id, values)
                except Exception as e:
                    app.logger.error(f"Error tracking form data: {str(e)}")


            # Get line items with prices
            app.logger.debug(f"Project details before lookup_prices: {project_details}")
            line_items = lookup_prices(project_details, price_list)
            app.logger.debug(f"Line items after lookup_prices: {line_items}")
            total_cost = line_items.sub_total

            # Convert Line_Items to dictionary for JSON serialization
            line_items_dict = line_items.dict()


            return render_template('estimate.html',
                                    project_details=project_details,
                                    total_cost=total_cost,
                                    customer=customer,
                                    line_items=line_items_dict,
                                    authenticated=True)
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error processing estimate: {error_msg}")

            if "429 RESOURCE_EXHAUSTED" in error_msg:
                flash('The AI service is currently at capacity. Please wait a few minutes and try again.', 'error')
            elif "Request payload size exceeds the limit" in error_msg:
                flash('The uploaded file is too large. Please reduce the file size or use a smaller file.', 'error')
            else:
                flash('Error processing your request. Please try again.', 'error')
            return redirect(url_for('estimate'))

    return render_template('estimate.html', form=form, authenticated=True)

@app.route('/generate_proposal', methods=['POST'])
def create_proposal():
    try:
        project_details = json.loads(request.form.get('project_details'))
        line_items_data = json.loads(request.form.get('line_items'))
        customer_data = json.loads(request.form.get('customer'))

        # Recreate Line_Items object
        line_items = Line_Items(lines=[
            Line_Item(**item) for item in line_items_data['lines']
        ])

        templates, _ = load_templates()
        if isinstance(templates, list):
            templates = [str(t) for t in templates]
        else:
            templates = [str(templates)]

        proposal = generate_proposal(project_details, customer_data, line_items, templates)
        app.logger.debug(f"Customer Data: {customer_data}")
        return render_template('proposal.html', 
                            proposal=proposal,
                            raw_proposal=proposal,  # For markdown editing
                            customer=customer_data,
                            authenticated=True)
    except Exception as e:
        logging.error(f"Error generating proposal: {str(e)}")
        flash('Error generating proposal. Please try again.', 'error')
        return redirect(url_for('estimate'))

@app.route('/save_proposal', methods=['POST'])
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
def save_to_drive():
    if 'credentials' not in session:
        return redirect(url_for('login'))

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
    response = requests.get('https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {session["credentials"]["token"]}'})
    authenticated = response.status_code == 200
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

    return redirect(url_for('price_list'))

#if __name__ == '__main__':
 #   app.run(host='0.0.0.0', port=5000, debug=True)