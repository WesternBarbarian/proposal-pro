import os
import json
import logging
from datetime import datetime
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allow OAuth over HTTP for development
from flask import Flask, render_template, request, flash, redirect, url_for, make_response, session
from oauth_config import create_oauth_flow
from google_services import create_folder_if_not_exists, create_doc_in_folder
from markupsafe import Markup
from flask_session import Session
import markdown2
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
from ai_helper import analyze_project, extract_customer, generate_proposal, Customer, generate_price_list, lookup_prices, Line_Items, Line_Item

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

class ProjectForm(FlaskForm):
    project_description = TextAreaField('Project Description', validators=[DataRequired()])
    submit = SubmitField('Generate Estimate')

class PriceListForm(FlaskForm):
    price_description = TextAreaField('Price Description', validators=[DataRequired()])
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

@app.route('/')
def index():
    app.logger.info("Home route was accessed")
    credentials = session.get('credentials')
    return render_template('index.html', authenticated=credentials is not None)

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
def estimate():
    form = ProjectForm()
    if form.validate_on_submit():
        try:
            # Extract customer information and project details using AI
            project_details = analyze_project(form.project_description.data)
            app.logger.debug(f"Project details returned from analyze_project: {project_details}")
            price_list = load_price_list()

            customer = extract_customer(form.project_description.data)


            # Get line items with prices
            line_items = lookup_prices(project_details, price_list)
            total_cost = line_items.sub_total

            # Convert Line_Items to dictionary for JSON serialization
            line_items_dict = line_items.dict()

            
            return render_template('estimate.html',
                                    project_details=project_details.dict(),
                                    total_cost=total_cost,
                                    customer=customer.dict(),
                                    line_items=line_items_dict)
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error processing estimate: {error_msg}")
            
            if "429 RESOURCE_EXHAUSTED" in error_msg:
                flash('The AI service is currently at capacity. Please wait a few minutes and try again.', 'error')
            else:
                flash('Error processing your request. Please try again.', 'error')
            return redirect(url_for('estimate'))

    return render_template('estimate.html', form=form)

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

        customer = Customer(**customer_data)
        proposal = generate_proposal(project_details, customer, line_items)
        app.logger.debug(f"Customer Data: {customer}")
        return render_template('proposal.html', 
                            proposal=proposal,
                            raw_proposal=proposal)  # For markdown editing
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
        customer_data = json.loads(request.form.get('customer', '{}'))
        folder_id = create_folder_if_not_exists('proposal-pro')
        
        if not folder_id:
            flash('Please log in to save to Google Drive.', 'error')
            return redirect(url_for('login'))
            
        # Sanitize customer name for filename
        customer_name = ''.join(char for char in customer_data.get('name', 'Unknown') 
                              if char.isalnum() or char in ' -_').strip()
        doc_id = create_doc_in_folder(
            f"Proposal - {customer_name} - {datetime.now().strftime('%Y-%m-%d')}",
            content,
            folder_id
        )
        
        flash('Proposal saved to Google Drive successfully!', 'success')
        return redirect(url_for('estimate'))
    except Exception as e:
        logging.error(f"Error saving to Google Drive: {str(e)}")
        flash('Error saving to Google Drive. Please try again.', 'error')
        return redirect(url_for('estimate'))

@app.route('/price-list', methods=['GET', 'POST'])
def price_list():
    form = PriceListForm()
    current_prices = load_price_list()
    return render_template('price_list.html', 
                          form=form, 
                          current_prices=current_prices)



@app.route('/generate-price-list', methods=['POST'])
def generate_price_list_route():
    app.logger.debug(f"Form Data: {request.form}")
    app.logger.debug(f"Headers: {dict(request.headers)}")
    app.logger.debug(f"CSRF Token from form: {request.form.get('csrf_token')}")
    app.logger.debug(f"CSRF Token from session: {session.get('csrf_token')}")

    form = PriceListForm()
    app.logger.debug(f"Form errors: {form.errors}")
    app.logger.debug(f"Form validated: {form.validate()}")

    if form.validate_on_submit():
        try:
            app.logger.info("Form validation successful")
            items = generate_price_list(form.price_description.data)
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
        flash('Invalid CSRF token or form submission.', 'error')

    return redirect(url_for('price_list'))

@app.route('/delete-price', methods=['POST'])
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

#if __name__ == '__main__':
 #   app.run(host='0.0.0.0', port=5000, debug=True)