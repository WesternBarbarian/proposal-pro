import os
import json
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify
from template_manager import load_templates, save_templates, add_template, delete_template
from blueprints.auth import require_auth

proposals_bp = Blueprint('proposals', __name__)

@proposals_bp.route('/proposal-templates')
@require_auth
def proposal_templates():
    templates = load_templates()
    return render_template('proposal_templates.html', templates=templates, authenticated=True)

@proposals_bp.route('/add-template', methods=['POST'])
@require_auth
def add_template_route():
    template_text = request.form.get('template_text')
    if not template_text:
        flash('Template text is required.', 'error')
        return redirect(url_for('proposals.proposal_templates'))
    
    success, message = add_template(template_text)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('proposals.proposal_templates'))

@proposals_bp.route('/delete-template/<template_id>', methods=['POST'])
@require_auth
def delete_template_route(template_id):
    success, message = delete_template(template_id)
    flash(message, 'success' if success else 'error')
    return redirect(url_for('proposals.proposal_templates'))