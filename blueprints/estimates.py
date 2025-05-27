import os
import json
import uuid
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, send_file, jsonify, make_response
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import TextAreaField, SubmitField
from ai_helper import extract_project_data, extract_project_data_from_image, lookup_prices
from blueprints.auth import require_auth
from google_services import create_doc_in_folder, create_folder_if_not_exists, append_to_sheet, create_tracking_sheet_if_not_exists
from template_manager import load_templates
from db.estimates import create_estimate, get_estimate, update_estimate

estimates_bp = Blueprint('estimates', __name__)

class ProjectForm(FlaskForm):
    project_description = TextAreaField('Project Description')
    file = FileField('Upload File', validators=[
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'heic'], 'Only PDF, PNG, JPEG, and HEIC files allowed!')
    ])
    submit_button = SubmitField('Generate Estimate')



def load_price_list(user_email):
    """Load price list from database for user's tenant."""
    from db.price_lists import get_price_list
    return get_price_list(user_email)

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
        user_email = session.get('user_email')
        if not user_email:
            flash('User session expired. Please log in again.', 'error')
            return redirect(url_for('auth.login'))

        price_list = load_price_list(user_email)
        if not price_list:
            flash('No price list found for your account. Please set up your price list first.', 'warning')
            # Continue with empty price list to allow estimate generation
            price_list = {}

        line_items = lookup_prices(project_details, price_list)
        total_cost = line_items.sub_total
        line_items_dict = line_items.dict()

        # Save estimate to database
        logging.info(f"Attempting to save estimate for user: {user_email}")
        logging.debug(f"Customer data: {customer}")
        logging.debug(f"Project details: {project_details}")
        logging.debug(f"Line items: {line_items_dict}")
        logging.debug(f"Total cost: {total_cost}")

        estimate_id = create_estimate(
            user_email=user_email,
            customer=customer,
            project_details=project_details,
            line_items=line_items_dict,
            total_cost=total_cost
        )

        if not estimate_id:
            logging.error(f"Failed to save estimate to database for user: {user_email}")
            flash('Failed to save estimate. Please try again.', 'error')
            return redirect(url_for('estimates.estimate'))

        logging.info(f"Successfully saved estimate to database with ID: {estimate_id}")

        # Store estimate result in session for immediate use
        estimate_result = {
            'customer': customer,
            'project_details': project_details,
            'line_items': line_items_dict,
            'total_cost': total_cost,
            'estimate_id': estimate_id
        }

        session['estimate_result'] = estimate_result
        session.modified = True

        logging.debug(f"Estimate processed successfully. Total cost: ${total_cost:.2f}, ID: {estimate_id}")

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

        # If not in session, try to load from database using estimate_id from URL params
        if not estimate_result:
            estimate_id = request.args.get('estimate_id')
            if estimate_id:
                user_email = session.get('user_email')
                if user_email:
                    estimate_result = get_estimate(estimate_id, user_email)
                    if estimate_result:
                        # Re-populate session with data from database
                        session['estimate_result'] = estimate_result
                        session.modified = True
                    else:
                        flash('Estimate not found or access denied.', 'error')
                        return redirect(url_for('estimates.estimate'))
                else:
                    flash('User session expired. Please log in again.', 'error')
                    return redirect(url_for('auth.login'))
            else:
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
            # Generate a proposal using AI helper
            logging.info("Generating proposal using AI helper")

            customer = estimate_result['customer']
            project_details = estimate_result['project_details']
            line_items = estimate_result['line_items']

            # Import generate_proposal from ai_helper
            from ai_helper import generate_proposal

            try:
                # Call the AI helper function to generate the proposal
                raw_proposal = generate_proposal(
                    project_details=project_details,
                    customer=customer,
                    line_items=line_items,
                    templates=templates
                )

                logging.info("AI proposal generated successfully")

                if not raw_proposal:
                    logging.warning("AI generated an empty proposal, falling back to template")
                    # Fallback to a simple template if AI fails
                    customer_name = customer.get('name', 'Customer')
                    total_cost = estimate_result['total_cost']
                    total_cost_formatted = f"${total_cost:.2f}"

                    raw_proposal = f"# Project Proposal for {customer_name}\n\n"
                    raw_proposal += f"Total Cost: {total_cost_formatted}\n\n"
                    raw_proposal += "## Project Details\n\n"
                    raw_proposal += f"Project Address: {customer.get('project_address', 'Same as customer address')}\n\n"

                    # Format line items as markdown table
                    raw_proposal += "## Line Items\n\n"
                    raw_proposal += "| Item | Quantity | Unit | Price | Total |\n"
                    raw_proposal += "|------|----------|------|-------|-------|\n"

                    for item in line_items['lines']:
                        raw_proposal += f"| {item['name']} | {item['quantity']} | {item['unit']} | ${item['price']:.2f} | ${item['total']:.2f} |\n"

                    raw_proposal += f"\n**Total: ${total_cost:.2f}**"

                    # Add contact information
                    raw_proposal += "\n\nContact Details:\n\n"
                    raw_proposal += f"- Name: {customer.get('name', 'Unknown')}\n"
                    raw_proposal += f"- Phone: {customer.get('phone', 'Unknown')}\n"
                    raw_proposal += f"- Email: {customer.get('email', 'Unknown')}\n"
                    raw_proposal += f"- Address: {customer.get('address', 'Unknown')}\n"
            except Exception as e:
                logging.error(f"Error generating AI proposal: {str(e)}", exc_info=True)
                flash(f"Error generating AI proposal: {str(e)}", "warning")

                # Fallback to simple template
                customer_name = customer.get('name', 'Customer')
                total_cost = estimate_result['total_cost']
                raw_proposal = f"# Project Proposal for {customer_name}\n\nTotal Cost: ${total_cost:.2f}"
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

            # Use the template from default_template.json
            # First, prepare replacement values
            customer_name = customer.get('name', 'Customer')
            project_scope = project_details.get('notes', 'home improvement project')
            total_cost_formatted = f"${total_cost:.2f}"
            start_date = "as soon as possible"  # This could be configurable in the future

            # Now use the default template and replace placeholders
            raw_proposal = default_template

            # Replace common placeholders in the template
            raw_proposal = raw_proposal.replace("[Homeowner's Name]", customer_name)
            raw_proposal = raw_proposal.replace("[brief project scope", project_scope)
            raw_proposal = raw_proposal.replace("[$XX,XXX]", total_cost_formatted)
            raw_proposal = raw_proposal.replace("[start date]", start_date)

            # Append line items to the proposal
            raw_proposal += "\n\n## Project Details\n\n"
            raw_proposal += f"Project Address: {customer.get('project_address', 'Same as customer address')}\n\n"
            raw_proposal += "## Line Items\n\n"
            raw_proposal += line_items_text

            # Add contact information at the end
            raw_proposal += "\n\nContact Details:\n\n"
            raw_proposal += f"- Name: {customer.get('name', 'Unknown')}\n"
            raw_proposal += f"- Phone: {customer.get('phone', 'Unknown')}\n"
            raw_proposal += f"- Email: {customer.get('email', 'Unknown')}\n"
            raw_proposal += f"- Address: {customer.get('address', 'Unknown')}\n"
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
        # Get the edited proposal content from the form
        edited_proposal = request.form.get('edited_proposal')
        if not edited_proposal:
            flash('No proposal content provided.', 'error')
            return redirect(url_for('estimates.create_proposal'))

        # Update session with edited content
        session['proposal_content'] = edited_proposal
        session.modified = True

        # Update proposal in database if we have a proposal ID
        proposal_id = session.get('proposal_id')
        user_email = session.get('user_email')

        if proposal_id and user_email:
            from db.proposals import update_proposal
            success = update_proposal(
                proposal_id=proposal_id,
                proposal_content=edited_proposal,
                user_email=user_email
            )
            if success:
                logging.info(f"Updated proposal {proposal_id} in database")
            else:
                logging.warning(f"Failed to update proposal {proposal_id} in database")

        # Create filename
        estimate_result = session.get('estimate_result')
        if estimate_result and 'customer' in estimate_result:
            customer_name = estimate_result['customer'].get('name', 'Customer')
            safe_name = "".join(c for c in customer_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"proposal_{safe_name}.md"
        else:
            filename = "proposal.md"

        # Create response with file download
        response = make_response(edited_proposal)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Type'] = 'text/markdown'

        return response

    except Exception as e:
        logging.error(f"Error saving proposal: {str(e)}", exc_info=True)
        flash(f'Error saving proposal: {str(e)}', 'error')
        return redirect(url_for('estimates.create_proposal'))


@estimates_bp.route('/update_estimate_data', methods=['POST'])
@require_auth
def update_estimate_data():
    try:
        # Get current estimate result from session
        estimate_result = session.get('estimate_result')
        if not estimate_result:
            return {'success': False, 'message': 'No estimate data found in session'}, 400

        # Update customer information
        customer = estimate_result['customer']
        customer['name'] = request.form.get('customer_name', customer.get('name', ''))
        customer['phone'] = request.form.get('customer_phone', customer.get('phone', ''))
        customer['email'] = request.form.get('customer_email', customer.get('email', ''))
        customer['address'] = request.form.get('customer_address', customer.get('address', ''))
        customer['project_address'] = request.form.get('customer_project_address', customer.get('project_address', ''))

        # Update project details
        project_details = estimate_result['project_details']
        project_details['notes'] = request.form.get('project_notes', project_details.get('notes', ''))

        # Update the estimate result in session
        estimate_result['customer'] = customer
        estimate_result['project_details'] = project_details
        session['estimate_result'] = estimate_result
        session.modified = True

        # Update the estimate in the database
        estimate_id = estimate_result.get('estimate_id')
        user_email = session.get('user_email')

        if estimate_id and user_email:
            success = update_estimate(
                estimate_id=estimate_id,
                user_email=user_email,
                customer=customer,
                project_details=project_details
            )

            if not success:
                logging.error("Failed to update estimate in database")
                return jsonify({'success': False, 'message': 'Failed to update estimate in database'}), 500

        logging.info("Estimate data updated successfully")
        return jsonify({'success': True, 'message': 'Estimate data updated successfully'})

    except Exception as e:
        logging.error(f"Error updating estimate data: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@estimates_bp.route('/update_line_items', methods=['POST'])
@require_auth
def update_line_items():
    try:
        # Get current estimate result from session
        estimate_result = session.get('estimate_result')
        if not estimate_result:
            return jsonify({'success': False, 'message': 'No estimate data found in session'}), 400

        # Get the updated line items from request
        data = request.get_json()
        if not data or 'line_items' not in data:
            return jsonify({'success': False, 'message': 'No line items data provided'}), 400

        # Update the line items in the estimate result
        estimate_result['line_items'] = data['line_items']
        estimate_result['total_cost'] = data['line_items']['sub_total']

        # Update session
        session['estimate_result'] = estimate_result
        session.modified = True

        # Update the estimate in the database
        estimate_id = estimate_result.get('estimate_id')
        user_email = session.get('user_email')

        if estimate_id and user_email:
            success = update_estimate(
                estimate_id=estimate_id,
                user_email=user_email,
                line_items=data['line_items'],
                total_cost=data['line_items']['sub_total']
            )

            if not success:
                logging.error("Failed to update line items in database")
                return jsonify({'success': False, 'message': 'Failed to update line items in database'}), 500

        logging.info("Line items updated successfully")
        return jsonify({
            'success': True, 
            'message': 'Line items updated successfully',
            'total_cost': data['line_items']['sub_total']
        })

    except Exception as e:
        logging.error(f"Error updating line items: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@estimates_bp.route('/debug_estimates', methods=['GET'])
@require_auth
def debug_estimates():
    """Debug route to show raw estimates data"""
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'error': 'No user email in session'}), 400

        from db.tenants import get_tenant_id_by_user_email
        from db.connection import execute_query

        tenant_id = get_tenant_id_by_user_email(user_email)
        logging.info(f"Debug: User {user_email} has tenant_id: {tenant_id}")

        # Get raw estimates data
        query = """
        SELECT estimate_id, tenant_id, customer_data, total_cost, created_at, created_by_email
        FROM estimates 
        WHERE tenant_id = %s AND deleted_at IS NULL
        ORDER BY created_at DESC
        """

        raw_estimates = execute_query(query, (tenant_id,), fetch=True)

        # Also get all estimates regardless of tenant for debugging
        all_estimates_query = """
        SELECT estimate_id, tenant_id, customer_data, total_cost, created_at, created_by_email
        FROM estimates 
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC
        """

        all_estimates = execute_query(all_estimates_query, fetch=True)

        return jsonify({
            'user_email': user_email,
            'tenant_id': str(tenant_id) if tenant_id else None,
            'estimates_for_tenant': len(raw_estimates),
            'all_estimates_in_db': len(all_estimates),
            'tenant_estimates': [
                {
                    'estimate_id': str(row['estimate_id']),
                    'customer_name': json.loads(row['customer_data']).get('name', 'Unknown'),
                    'total_cost': float(row['total_cost']),
                    'created_by': row['created_by_email'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                } for row in raw_estimates
            ],
            'all_estimates': [
                {
                    'estimate_id': str(row['estimate_id']),
                    'tenant_id': str(row['tenant_id']),
                    'customer_name': json.loads(row['customer_data']).get('name', 'Unknown'),
                    'total_cost': float(row['total_cost']),
                    'created_by': row['created_by_email'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                } for row in all_estimates
            ]
        })

    except Exception as e:
        logging.error(f"Error in debug_estimates: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@estimates_bp.route('/list_estimates', methods=['GET'])
@require_auth
def list_estimates():
    """List all estimates for the current user's tenant"""
    try:
        user_email = session.get('user_email')
        if not user_email:
            flash('User session expired. Please log in again.', 'error')
            return redirect(url_for('auth.login'))

        from db.estimates import get_estimates_for_tenant
        estimates = get_estimates_for_tenant(user_email)

        logging.info(f"Found {len(estimates)} estimates for user {user_email}")

        return render_template('estimate_list.html', 
                             estimates=estimates, 
                             authenticated=True)
    except Exception as e:
        logging.error(f"Error listing estimates: {str(e)}", exc_info=True)
        flash(f'Error listing estimates: {str(e)}', 'error')
        return redirect(url_for('estimates.estimate'))

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
        customer_name = customer.get('name', 'Unknown')
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
                customer.get('email', ''),
                customer.get('phone', ''),
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