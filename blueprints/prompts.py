
import os
import json
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired
from prompt_manager import get_prompt_manager
from blueprints.auth import require_auth
from db.prompts import get_active_prompts, get_prompt_versions

prompts_bp = Blueprint('prompts', __name__)

class PromptForm(FlaskForm):
    """Form for creating/editing prompts"""
    name = StringField('Prompt Name', validators=[DataRequired()])
    description = StringField('Description')
    system_instruction = TextAreaField('System Instruction')
    user_prompt = TextAreaField('User Prompt Template', validators=[DataRequired()])
    submit = SubmitField('Save Prompt')

class RollbackForm(FlaskForm):
    """Form for rolling back to a previous prompt version"""
    version = SelectField('Version', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Rollback to Version')

@prompts_bp.route('/prompts')
@require_auth
def list_prompts():
    """List all available prompts"""
    tenant_id = session.get('tenant_id', '00000000-0000-0000-0000-000000000001')
    prompts = []
    
    try:
        db_prompts = get_active_prompts(tenant_id)
        for prompt in db_prompts:
            prompts.append({
                'name': prompt['name'],
                'description': prompt.get('description', ''),
                'has_system_instruction': bool(prompt.get('system_instruction')),
                'user_prompt_preview': prompt.get('user_prompt', '')[:100] + '...' if len(prompt.get('user_prompt', '')) > 100 else prompt.get('user_prompt', ''),
                'version': prompt.get('version', 1),
                'created_at': prompt.get('created_at'),
                'created_by_email': prompt.get('created_by_email')
            })
    except Exception as e:
        flash(f"Error loading prompts: {str(e)}", 'error')
        logging.error(f"Error loading prompts: {str(e)}")
    
    return render_template('prompts.html', prompts=prompts, authenticated=True)

@prompts_bp.route('/prompts/new', methods=['GET', 'POST'])
@require_auth
def new_prompt():
    """Create a new prompt"""
    form = PromptForm()
    
    if form.validate_on_submit():
        created_by_email = session.get('user_email', 'unknown@unknown.com')
        
        try:
            prompt_manager = get_prompt_manager()
            success = prompt_manager.create_or_update_prompt(
                name=form.name.data,
                description=form.description.data or '',
                system_instruction=form.system_instruction.data or '',
                user_prompt=form.user_prompt.data,
                created_by_email=created_by_email
            )
            
            if success:
                flash(f"Prompt '{form.name.data}' created successfully", 'success')
                return redirect(url_for('prompts.list_prompts'))
            else:
                flash(f"Error creating prompt '{form.name.data}'", 'error')
        except Exception as e:
            flash(f"Error creating prompt: {str(e)}", 'error')
    
    return render_template('prompt_form.html', form=form, mode='new', authenticated=True)

@prompts_bp.route('/prompts/edit/<name>', methods=['GET', 'POST'])
@require_auth
def edit_prompt(name):
    """Edit an existing prompt"""
    prompt_manager = get_prompt_manager()
    prompt = prompt_manager.get_prompt(name)
    
    if not prompt:
        flash(f"Prompt '{name}' not found", 'error')
        return redirect(url_for('prompts.list_prompts'))
        
    form = PromptForm()
    
    if request.method == 'GET':
        form.name.data = name
        form.description.data = prompt.get('description', '')
        form.system_instruction.data = prompt.get('system_instruction', '')
        form.user_prompt.data = prompt.get('user_prompt', '')
    
    if form.validate_on_submit():
        created_by_email = session.get('user_email', 'unknown@unknown.com')
        
        try:
            # For edit, we always create a new version (database handles versioning)
            success = prompt_manager.create_or_update_prompt(
                name=form.name.data,
                description=form.description.data or '',
                system_instruction=form.system_instruction.data or '',
                user_prompt=form.user_prompt.data,
                created_by_email=created_by_email
            )
            
            if success:
                flash(f"Prompt '{form.name.data}' updated successfully", 'success')
                return redirect(url_for('prompts.list_prompts'))
            else:
                flash(f"Error updating prompt '{form.name.data}'", 'error')
        except Exception as e:
            flash(f"Error updating prompt: {str(e)}", 'error')
    
    return render_template('prompt_form.html', form=form, mode='edit', authenticated=True)

@prompts_bp.route('/prompts/delete/<name>', methods=['POST'])
@require_auth
def delete_prompt(name):
    """Delete a prompt"""
    try:
        prompt_manager = get_prompt_manager()
        success = prompt_manager.delete_prompt(name)
        
        if success:
            flash(f"Prompt '{name}' deleted successfully", 'success')
        else:
            flash(f"Error deleting prompt '{name}'", 'error')
    except Exception as e:
        flash(f"Error deleting prompt: {str(e)}", 'error')
            
    return redirect(url_for('prompts.list_prompts'))

@prompts_bp.route('/prompts/versions/<name>')
@require_auth
def view_prompt_versions(name):
    """View all versions of a prompt"""
    tenant_id = session.get('tenant_id', '00000000-0000-0000-0000-000000000001')
    
    try:
        versions = get_prompt_versions(tenant_id, name)
        if not versions:
            flash(f"Prompt '{name}' not found", 'error')
            return redirect(url_for('prompts.list_prompts'))
            
        return render_template('prompt_versions.html', prompt_name=name, versions=versions, authenticated=True)
    except Exception as e:
        flash(f"Error loading prompt versions: {str(e)}", 'error')
        return redirect(url_for('prompts.list_prompts'))

@prompts_bp.route('/prompts/rollback/<name>', methods=['GET', 'POST'])
@require_auth
def rollback_prompt(name):
    """Rollback a prompt to a previous version"""
    tenant_id = session.get('tenant_id', '00000000-0000-0000-0000-000000000001')
    
    try:
        versions = get_prompt_versions(tenant_id, name)
        if not versions:
            flash(f"Prompt '{name}' not found", 'error')
            return redirect(url_for('prompts.list_prompts'))
        
        form = RollbackForm()
        # Populate version choices (exclude current active version)
        inactive_versions = [(v['version'], f"Version {v['version']} - {v['created_at'].strftime('%Y-%m-%d %H:%M')}") 
                           for v in versions if not v['is_active']]
        form.version.choices = inactive_versions
        
        if form.validate_on_submit():
            created_by_email = session.get('user_email', 'unknown@unknown.com')
            prompt_manager = get_prompt_manager()
            
            success = prompt_manager.rollback_prompt_version(name, form.version.data, created_by_email)
            if success:
                flash(f"Prompt '{name}' rolled back to version {form.version.data} successfully", 'success')
                return redirect(url_for('prompts.list_prompts'))
            else:
                flash(f"Error rolling back prompt '{name}'", 'error')
        
        return render_template('prompt_rollback.html', form=form, prompt_name=name, versions=versions, authenticated=True)
    except Exception as e:
        flash(f"Error during rollback: {str(e)}", 'error')
        return redirect(url_for('prompts.list_prompts'))

@prompts_bp.route('/prompts/migrate', methods=['POST'])
@require_auth
def migrate_prompts():
    """Migrate prompts from files to database"""
    try:
        created_by_email = session.get('user_email', 'migration@system.com')
        tenant_id = session.get('tenant_id')
        
        # If no tenant_id in session, try to get or create one
        if not tenant_id:
            from db.tenants import get_tenant_id_by_user_email
            from db.connection import execute_query
            
            user_email = session.get('user_email')
            if user_email:
                tenant_id = get_tenant_id_by_user_email(user_email)
            
            # If still no tenant, get the first available tenant
            if not tenant_id:
                result = execute_query("SELECT id FROM tenants WHERE deleted_at IS NULL LIMIT 1;")
                if result and len(result) > 0:
                    tenant_id = result[0]['id']
                    session['tenant_id'] = tenant_id
        
        if not tenant_id:
            flash("No tenant found. Please contact administrator.", 'error')
            return redirect(url_for('prompts.list_prompts'))
        
        prompt_manager = get_prompt_manager()
        success = prompt_manager.migrate_file_prompts(created_by_email, tenant_id)
        
        if success:
            flash("Prompts migrated to database successfully", 'success')
        else:
            flash("Error migrating prompts to database", 'error')
    except Exception as e:
        flash(f"Error during migration: {str(e)}", 'error')
        logging.error(f"Migration error: {str(e)}")
        
    return redirect(url_for('prompts.list_prompts'))
