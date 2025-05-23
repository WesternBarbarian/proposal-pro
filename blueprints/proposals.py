
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify
from template_manager import load_templates, add_template, delete_template
from blueprints.auth import require_auth
from db.templates import get_templates as db_get_templates

# Configure logging
logger = logging.getLogger(__name__)

proposals_bp = Blueprint('proposals', __name__)

@proposals_bp.route('/proposal-templates')
@require_auth
def proposal_templates():
    try:
        templates, using_custom = load_templates()
        return render_template('proposal_templates.html', templates=templates, using_custom=using_custom, authenticated=True)
    except Exception as e:
        logger.error(f"Error loading proposal templates: {e}")
        flash('An error occurred while loading templates.', 'error')
        return render_template('proposal_templates.html', templates=[], using_custom=False, authenticated=True)

@proposals_bp.route('/add-template', methods=['POST'])
@require_auth
def add_template_route():
    template_text = request.form.get('template')
    if not template_text:
        flash('Template text is required.', 'error')
        return redirect(url_for('proposals.proposal_templates'))
    
    try:
        success, message = add_template(template_text)
        flash(message, 'success' if success else 'error')
    except Exception as e:
        logger.error(f"Error adding template: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('proposals.proposal_templates'))

@proposals_bp.route('/delete-template/<template_id>', methods=['POST'])
@require_auth
def delete_template_route(template_id):
    try:
        templates, using_custom = load_templates()
        
        if not using_custom:
            flash('Cannot delete default templates. Add a custom template first.', 'error')
            return redirect(url_for('proposals.proposal_templates'))
            
        success, message = delete_template(template_id)
        flash(message, 'success' if success else 'error')
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        flash(f'An error occurred: {str(e)}', 'error')
    
    return redirect(url_for('proposals.proposal_templates'))

@proposals_bp.route('/api/templates', methods=['GET'])
@require_auth
def get_templates_api():
    try:
        email = session.get('user_email')
        if not email:
            return jsonify({'error': 'User not authenticated'}), 401
        
        templates = db_get_templates(email)
        return jsonify({'templates': templates})
    except Exception as e:
        logger.error(f"Error retrieving templates: {e}")
        return jsonify({'error': str(e)}), 500
