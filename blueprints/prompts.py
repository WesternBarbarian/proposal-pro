
import os
import json
import logging
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired
from prompt_manager import get_prompt_manager
from blueprints.auth import require_auth

prompts_bp = Blueprint('prompts', __name__)

class PromptForm(FlaskForm):
    """Form for creating/editing prompts"""
    name = StringField('Prompt Name', validators=[DataRequired()])
    description = StringField('Description')
    system_instruction = TextAreaField('System Instruction')
    user_prompt = TextAreaField('User Prompt Template', validators=[DataRequired()])
    submit = SubmitField('Save Prompt')

@prompts_bp.route('/prompts')
@require_auth
def list_prompts():
    """List all available prompts"""
    prompt_manager = get_prompt_manager()
    prompts = []
    
    # Get names of all prompt files
    prompts_dir = prompt_manager.prompts_dir
    if os.path.exists(prompts_dir):
        for filename in os.listdir(prompts_dir):
            if filename.endswith('.json'):
                prompt_name = os.path.splitext(filename)[0]
                prompt = prompt_manager.get_prompt(prompt_name)
                if prompt:
                    prompts.append({
                        'name': prompt_name,
                        'description': prompt.get('description', ''),
                        'has_system_instruction': 'system_instruction' in prompt,
                        'user_prompt_preview': prompt.get('user_prompt', '')[:100] + '...' if len(prompt.get('user_prompt', '')) > 100 else prompt.get('user_prompt', '')
                    })
    
    return render_template('prompts.html', prompts=prompts, authenticated=True)

@prompts_bp.route('/prompts/new', methods=['GET', 'POST'])
@require_auth
def new_prompt():
    """Create a new prompt"""
    form = PromptForm()
    
    if form.validate_on_submit():
        prompt_data = {
            'name': form.name.data,
            'description': form.description.data,
            'user_prompt': form.user_prompt.data
        }
        
        if form.system_instruction.data:
            prompt_data['system_instruction'] = form.system_instruction.data
            
        # Save to file
        prompt_path = os.path.join('prompts', f"{form.name.data}.json")
        
        try:
            with open(prompt_path, 'w') as f:
                json.dump(prompt_data, f, indent=2)
                
            # Refresh prompts
            get_prompt_manager()._load_all_prompts()
            
            flash(f"Prompt '{form.name.data}' created successfully", 'success')
            return redirect(url_for('prompts.list_prompts'))
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
        prompt_data = {
            'name': form.name.data,
            'description': form.description.data,
            'user_prompt': form.user_prompt.data
        }
        
        if form.system_instruction.data:
            prompt_data['system_instruction'] = form.system_instruction.data
            
        # Save to file - handle rename case
        new_prompt_path = os.path.join('prompts', f"{form.name.data}.json")
        old_prompt_path = os.path.join('prompts', f"{name}.json")
        
        try:
            # If name changed, delete old file
            if form.name.data != name and os.path.exists(old_prompt_path):
                os.remove(old_prompt_path)
                
            with open(new_prompt_path, 'w') as f:
                json.dump(prompt_data, f, indent=2)
                
            # Refresh prompts
            get_prompt_manager()._load_all_prompts()
            
            flash(f"Prompt '{form.name.data}' updated successfully", 'success')
            return redirect(url_for('prompts.list_prompts'))
        except Exception as e:
            flash(f"Error updating prompt: {str(e)}", 'error')
    
    return render_template('prompt_form.html', form=form, mode='edit', authenticated=True)

@prompts_bp.route('/prompts/delete/<name>', methods=['POST'])
@require_auth
def delete_prompt(name):
    """Delete a prompt"""
    prompt_path = os.path.join('prompts', f"{name}.json")
    
    if not os.path.exists(prompt_path):
        flash(f"Prompt '{name}' not found", 'error')
    else:
        try:
            os.remove(prompt_path)
            # Refresh prompts
            get_prompt_manager()._load_all_prompts()
            flash(f"Prompt '{name}' deleted successfully", 'success')
        except Exception as e:
            flash(f"Error deleting prompt: {str(e)}", 'error')
            
    return redirect(url_for('prompts.list_prompts'))
