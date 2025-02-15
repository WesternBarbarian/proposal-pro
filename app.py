import os
import json
import logging
from flask import Flask, render_template, request, flash, redirect, url_for, make_response
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
from ai_helper import analyze_project, generate_proposal, Customer, generate_price_list, lookup_prices

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ["SESSION_SECRET"]
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
    except FileNotFoundError:
        return {}

# Save price list
def save_price_list(price_list):
    with open('price_list.json', 'w') as f:
        json.dump(price_list, f, indent=4)

@app.route('/')
def index():
    app.logger.info("Home route was accessed")  # Log an INFO message
    return render_template('index.html')
    

@app.route('/estimate', methods=['GET', 'POST'])
def estimate():
    form = ProjectForm()
    if form.validate_on_submit():
        try:
            # Extract customer information and project details using AI
            project_details = analyze_project(form.project_description.data)
            price_list = load_price_list()

            # Create Customer object from AI-extracted data
            customer = Customer(
                name=project_details.get('customer', {}).get('name', 'unknown'),
                phone=project_details.get('customer', {}).get('phone', 'unknown'),
                email=project_details.get('customer', {}).get('email', 'unknown'),
                address=project_details.get('customer', {}).get('address', 'unknown'),
                project_address=project_details.get('customer', {}).get('project_address', 'same')
            )

            # Get line items with prices
            line_items = lookup_prices(project_details, price_list)
            total_cost = line_items.sub_total

            return render_template('estimate.html',
                                    project_details=project_details,
                                    total_cost=total_cost,
                                    customer=customer,
                                    line_items=line_items)
        except Exception as e:
            logging.error(f"Error processing estimate: {str(e)}")
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

@app.route('/price-list', methods=['GET', 'POST'])
def price_list():
    form = PriceListForm()
    current_prices = load_price_list()
    return render_template('price_list.html', 
                         form=form, 
                         current_prices=current_prices,
                         units={})

@app.route('/generate-price-list', methods=['POST'])
def generate_price_list_route():
    form = PriceListForm()
    if form.validate_on_submit():
        try:
            
            # Generate price list using AI
            items = generate_price_list(form.price_description.data)
            app.logger.info(f"Logging: {items}") 

            

            # Save the new price list
            save_price_list(price_list)

            flash('Price list updated successfully!', 'success')
            return redirect(url_for('price_list'))
        except Exception as e:
            logging.error(f"Error generating price list: {str(e)}")
            flash('Error generating price list. Please try again.', 'error')

    return redirect(url_for('price_list'))

@app.route('/update-price', methods=['POST'])
def update_price():
    try:
        item = request.form.get('item')
        price = float(request.form.get('price'))

        if not item or price < 0:
            flash('Invalid price update request.', 'error')
            return redirect(url_for('price_list'))

        # Load current price list
        price_list = load_price_list()

        # Update price
        price_list[item] = price

        # Save updated price list
        save_price_list(price_list)

        flash('Price updated successfully!', 'success')
    except Exception as e:
        logging.error(f"Error updating price: {str(e)}")
        flash('Error updating price. Please try again.', 'error')

    return redirect(url_for('price_list'))

#if __name__ == '__main__':
 #   app.run(host='0.0.0.0', port=5000, debug=True)