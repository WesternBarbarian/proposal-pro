import os
import json
import logging
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
from ai_helper import analyze_project, generate_proposal, Customer

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

class ProjectForm(FlaskForm):
    project_description = TextAreaField('Project Description', validators=[DataRequired()])
    submit = SubmitField('Generate Estimate')

# Load price list
def load_price_list():
    with open('price_list.json', 'r') as f:
        return json.load(f)

@app.route('/')
def index():
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

            # Calculate estimated costs
            total_cost = 0
            for item in project_details['items']:
                if item['type'] in price_list:
                    total_cost += price_list[item['type']] * item['quantity']

            return render_template('estimate.html',
                                project_details=project_details,
                                total_cost=total_cost,
                                customer=customer)
        except Exception as e:
            logging.error(f"Error processing estimate: {str(e)}")
            flash('Error processing your request. Please try again.', 'error')
            return redirect(url_for('estimate'))

    return render_template('estimate.html', form=form)

@app.route('/generate_proposal', methods=['POST'])
def create_proposal():
    try:
        project_details = request.form.get('project_details')
        total_cost = float(request.form.get('total_cost'))
        customer_data = json.loads(request.form.get('customer'))

        customer = Customer(**customer_data)
        proposal = generate_proposal(project_details, customer, total_cost)

        return render_template('proposal.html', proposal=proposal)
    except Exception as e:
        logging.error(f"Error generating proposal: {str(e)}")
        flash('Error generating proposal. Please try again.', 'error')
        return redirect(url_for('estimate'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)