import os
import json
import uuid
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import TextAreaField, SubmitField
from ai_helper import extract_project_data, extract_project_data_from_image, lookup_prices
from blueprints.auth import require_auth
from google_services import create_doc_in_folder, create_folder_if_not_exists, append_to_sheet, create_tracking_sheet_if_not_exists
from template_manager import load_templates

estimates_bp = Blueprint('estimates', __name__)

class ProjectForm(FlaskForm):
    project_description = TextAreaField('Project Description')
    file = FileField('Upload File', validators=[
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'heic'], 'Only PDF, PNG, JPEG, and HEIC files allowed!')
    ])
    submit_button = SubmitField('Generate Estimate')

# Unique identifier for this estimate session
ESTIMATE_ID = str(uuid.uuid4())

def load_price_list():
    try:
        with open('price_list.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

@estimates_bp.route('/estimate', methods=['GET'])
@require_auth
def estimate():
    form = ProjectForm()
    return render_template('estimate.html', form=form, authenticated=True)

@estimates_bp.route('/process_estimate', methods=['POST'])
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
            return redirect(url_for('estimates.estimate'))

        # Validate extracted data
        if not customer or not project_details:
            flash('Failed to extract project details. Please try again.', 'error')
            return redirect(url_for('estimates.estimate'))

        # Price calculation
        price_list = load_price_list()
        line_items = lookup_prices(project_details, price_list)
        total_cost = line_items.sub_total
        line_items_dict = line_items.dict()

        # Store data in global variable AND session
        estimate_result = {
            'customer': customer,
            'project_details': project_details,
            'line_items': line_items_dict,
            'total_cost': total_cost,
            'estimate_id': ESTIMATE_ID
        }
        
        # Double-store the results in both session and application config to ensure persistence
        session['estimate_result'] = estimate_result
        session.modified = True
        
        logging.debug(f"Estimate processed successfully. Total cost: ${total_cost:.2f}")
        
        # Save data as a JSON file (backup persistence mechanism)
        try:
            with open(f'estimate_{ESTIMATE_ID}.json', 'w') as f:
                json.dump(estimate_result, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving estimate data to file: {str(e)}")
        
        return redirect(url_for('estimates.estimate_results'))
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Error processing estimate: {error_msg}", exc_info=True)
        flash(f'Error processing estimate: {error_msg}', 'error')
        return redirect(url_for('estimates.estimate'))

@estimates_bp.route('/estimate_results')
@require_auth
def estimate_results():
    try:
        # Try to get data from session first
        estimate_result = session.get('estimate_result')
        
        # If not in session, try to load from file (fallback)
        if not estimate_result:
            try:
                with open(f'estimate_{ESTIMATE_ID}.json', 'r') as f:
                    estimate_result = json.load(f)
                # Re-populate session with data from file
                session['estimate_result'] = estimate_result
                session.modified = True
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.error(f"Error loading estimate data from file: {str(e)}")
                flash('Estimate data not found. Please try again.', 'error')
                return redirect(url_for('estimates.estimate'))
                
        return render_template('estimate_results.html', 
                               customer=estimate_result['customer'],
                               project_details=estimate_result['project_details'],
                               line_items=estimate_result['line_items'],
                               total_cost=estimate_result['total_cost'],
                               authenticated=True)
    except Exception as e:
        logging.error(f"Error displaying estimate results: {str(e)}", exc_info=True)
        flash(f'Error displaying estimate results: {str(e)}', 'error')
        return redirect(url_for('estimates.estimate'))

@estimates_bp.route('/create_proposal', methods=['GET', 'POST'])
@require_auth
def create_proposal():
    # Add detailed logging
    logging.info(f"create_proposal called with method: {request.method}")
    
    # Handle POST request from estimate_results.html
    if request.method == 'POST':
        logging.info(f"Processing POST request to create_proposal")
        logging.debug(f"POST data: {request.form}")
        
        # Use data from session to maintain consistency
        estimate_result = session.get('estimate_result')
        logging.info(f"estimate_result from session: {estimate_result is not None}")
        
        if not estimate_result:
            logging.warning("No estimate data found in session")
            flash('No estimate data found. Please generate an estimate first.', 'error')
            return redirect(url_for('estimates.estimate'))
            
        # Load proposal templates
        templates, is_custom = load_templates()
        logging.info(f"Loaded {len(templates)} proposal templates (custom: {is_custom})")
        
        try:
            # Generate a default proposal using the first template
            logging.info("Generating default proposal from template")
            default_proposal = ""
            raw_proposal = ""
            
            if templates and len(templates) > 0:
                # Get the first template as default
                default_template = templates[0]  # Templates are already strings
                
                # Replace placeholders with actual data
                customer = estimate_result['customer']
                project_details = estimate_result['project_details']
                line_items = estimate_result['line_items']
                total_cost = estimate_result['total_cost']
                
                # Format line items as markdown table
                line_items_text = "| Item | Quantity | Unit | Price | Total |\n"
                line_items_text += "|------|----------|------|-------|-------|\n"
                
                for item in line_items['lines']:
                    line_items_text += f"| {item['name']} | {item['quantity']} | {item['unit']} | ${item['price']:.2f} | ${item['total']:.2f} |\n"
                
                line_items_text += f"\n**Total: ${total_cost:.2f}**"
                
                # Basic template with customer info and line items
                raw_proposal = f"""# Proposal for {customer.get('name', 'Customer')}

## Customer Information
- **Name:** {customer.get('name', 'Unknown')}
- **Phone:** {customer.get('phone', 'Unknown')}
- **Email:** {customer.get('email', 'Unknown')}
- **Address:** {customer.get('address', 'Unknown')}
- **Project Address:** {customer.get('project_address', 'Same as above')}

## Project Details
{project_details.get('notes', 'No additional notes')}

## Line Items
{line_items_text}

Thank you for your business!
"""
                # Store in session for later use
                session['proposal_content'] = raw_proposal
                session.modified = True
            
            # Return the proposal.html template with data from session
            logging.info("Rendering proposal.html with session data")
            return render_template('proposal.html', 
                            customer=estimate_result['customer'],
                            project_details=estimate_result['project_details'],
                            line_items=estimate_result['line_items'],
                            total_cost=estimate_result['total_cost'],
                            templates=templates,
                            proposal=raw_proposal,  # Provide the processed template
                            raw_proposal=raw_proposal,  # Raw markdown for editing
                            authenticated=True)
        except Exception as e:
            logging.error(f"Error rendering proposal template: {str(e)}", exc_info=True)
            flash(f"Error generating proposal: {str(e)}", "error")
            return redirect(url_for('estimates.estimate_results'))
    
    # Handle GET request
    logging.info(f"Processing GET request to create_proposal")
    estimate_result = session.get('estimate_result')
    logging.info(f"estimate_result from session: {estimate_result is not None}")
    
    if not estimate_result:
        logging.warning("No estimate data found in session")
        flash('No estimate data found. Please generate an estimate first.', 'error')
        return redirect(url_for('estimates.estimate'))
    
    # Load proposal templates
    templates, is_custom = load_templates()
    logging.info(f"Loaded {len(templates)} proposal templates (custom: {is_custom})")
    
    try:
        # Generate a default proposal using the first template
        logging.info("Generating default proposal from template for GET request")
        default_proposal = ""
        raw_proposal = ""
        
        if templates and len(templates) > 0:
            # Get the first template as default
            default_template = templates[0]  # Templates are already strings
            
            # Replace placeholders with actual data
            customer = estimate_result['customer']
            project_details = estimate_result['project_details']
            line_items = estimate_result['line_items']
            total_cost = estimate_result['total_cost']
            
            # Format line items as markdown table
            line_items_text = "| Item | Quantity | Unit | Price | Total |\n"
            line_items_text += "|------|----------|------|-------|-------|\n"
            
            for item in line_items['lines']:
                line_items_text += f"| {item['name']} | {item['quantity']} | {item['unit']} | ${item['price']:.2f} | ${item['total']:.2f} |\n"
            
            line_items_text += f"\n**Total: ${total_cost:.2f}**"
            
            # Basic template with customer info and line items
            raw_proposal = f"""# Proposal for {customer.get('name', 'Customer')}

## Customer Information
- **Name:** {customer.get('name', 'Unknown')}
- **Phone:** {customer.get('phone', 'Unknown')}
- **Email:** {customer.get('email', 'Unknown')}
- **Address:** {customer.get('address', 'Unknown')}
- **Project Address:** {customer.get('project_address', 'Same as above')}

## Project Details
{project_details.get('notes', 'No additional notes')}

## Line Items
{line_items_text}

Thank you for your business!
"""
            # Store in session for later use
            session['proposal_content'] = raw_proposal
            session.modified = True
        
        # Return the proposal.html template with data from session
        logging.info("Rendering proposal.html with session data")
        return render_template('proposal.html', 
                            customer=estimate_result['customer'],
                            project_details=estimate_result['project_details'],
                            line_items=estimate_result['line_items'],
                            total_cost=estimate_result['total_cost'],
                            templates=templates,
                            proposal=raw_proposal,  # Provide the processed template
                            raw_proposal=raw_proposal,  # Raw markdown for editing
                            authenticated=True)
    except Exception as e:
        logging.error(f"Error rendering proposal template: {str(e)}", exc_info=True)
        flash(f"Error generating proposal: {str(e)}", "error")
        return redirect(url_for('index'))

@estimates_bp.route('/save_proposal', methods=['POST'])
@require_auth
def save_proposal():
    try:
        proposal_content = request.form.get('proposal_content')
        if not proposal_content:
            flash('No proposal content provided.', 'error')
            return redirect(url_for('estimates.create_proposal'))
        
        # Store in session for later use
        session['proposal_content'] = proposal_content
        session.modified = True
        
        flash('Proposal saved successfully. You can now upload it to Google Drive.', 'success')
        return redirect(url_for('estimates.create_proposal'))
    except Exception as e:
        logging.error(f"Error saving proposal: {str(e)}", exc_info=True)
        flash(f'Error saving proposal: {str(e)}', 'error')
        return redirect(url_for('estimates.create_proposal'))

@estimates_bp.route('/save_to_drive', methods=['POST'])
@require_auth
def save_to_drive():
    try:
        # Get proposal content from session
        proposal_content = session.get('proposal_content')
        if not proposal_content:
            flash('No proposal content found. Please create a proposal first.', 'error')
            return redirect(url_for('estimates.create_proposal'))
        
        # Get customer info for naming
        estimate_result = session.get('estimate_result')
        if not estimate_result or 'customer' not in estimate_result:
            flash('Customer information not found. Please generate an estimate first.', 'error')
            return redirect(url_for('estimates.estimate'))
        
        customer = estimate_result['customer']
        customer_name = customer.get('customer_name', 'Unknown')
        project_address = customer.get('project_address', 'Unknown')
        
        # Create folder structure in Google Drive
        project_folder_id = create_folder_if_not_exists("Project Proposals")
        if not project_folder_id:
            flash('Failed to create or access Google Drive folder.', 'error')
            return redirect(url_for('estimates.create_proposal'))
            
        # Create spreadsheet for tracking if it doesn't exist
        spreadsheet_id = create_tracking_sheet_if_not_exists(project_folder_id)
        
        # Create document with proposal content
        doc_title = f"Proposal - {customer_name} - {project_address}"
        doc_info = create_doc_in_folder(doc_title, proposal_content, project_folder_id)
        
        if not doc_info:
            flash('Failed to create Google Doc.', 'error')
            return redirect(url_for('estimates.create_proposal'))
            
        # Add entry to tracking spreadsheet
        total_cost = estimate_result.get('total_cost', 0)
        
        # Append to tracking sheet
        values = [
            [
                customer_name,
                customer.get('customer_email', ''),
                customer.get('customer_phone', ''),
                project_address,
                f"${total_cost:.2f}",
                doc_info.get('doc_url', '')
            ]
        ]
        append_result = append_to_sheet(spreadsheet_id, values)
        
        if append_result:
            flash('Proposal saved to Google Drive successfully!', 'success')
        else:
            flash('Proposal saved to Google Drive, but failed to update tracking sheet.', 'warning')
            
        return redirect(url_for('estimates.create_proposal'))
        
    except Exception as e:
        logging.error(f"Error saving to Google Drive: {str(e)}", exc_info=True)
        flash(f'Error saving to Google Drive: {str(e)}', 'error')
        return redirect(url_for('estimates.create_proposal'))