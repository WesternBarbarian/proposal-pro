import os
import json
import logging
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from ai_helper import analyze_project, generate_proposal

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Load price list
def load_price_list():
    with open('price_list.json', 'r') as f:
        return json.load(f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/estimate', methods=['GET', 'POST'])
def estimate():
    if request.method == 'POST':
        project_description = request.form.get('project_description')
        if not project_description:
            flash('Please provide a project description', 'error')
            return redirect(url_for('estimate'))

        try:
            # Analyze project using Gemini AI
            project_details = analyze_project(project_description)
            price_list = load_price_list()
            
            # Calculate estimated costs
            total_cost = 0
            for item in project_details['items']:
                if item['type'] in price_list:
                    total_cost += price_list[item['type']] * item['quantity']

            return render_template('estimate.html',
                                project_details=project_details,
                                total_cost=total_cost)
        except Exception as e:
            logging.error(f"Error processing estimate: {str(e)}")
            flash('Error processing your request. Please try again.', 'error')
            return redirect(url_for('estimate'))

    return render_template('estimate.html')

@app.route('/generate_proposal', methods=['POST'])
def create_proposal():
    try:
        project_details = request.form.get('project_details')
        total_cost = request.form.get('total_cost')
        
        # Generate proposal using Gemini AI
        proposal = generate_proposal(project_details, total_cost)
        
        return render_template('proposal.html', proposal=proposal)
    except Exception as e:
        logging.error(f"Error generating proposal: {str(e)}")
        flash('Error generating proposal. Please try again.', 'error')
        return redirect(url_for('estimate'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
