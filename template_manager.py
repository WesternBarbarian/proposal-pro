
import logging
from db.templates import get_templates, save_template, delete_template as db_delete_template

# Configure logging
logger = logging.getLogger(__name__)

def load_templates():
    """
    Load templates from the database for the current user.
    Returns a tuple (templates, using_custom) where:
    - templates is a list of template strings
    - using_custom indicates if these are custom templates
    """
    from flask import session
    email = session.get('user_email')
    
    if not email:
        logger.warning("No user email found in session, returning empty templates")
        return ["Please log in to access templates."], False
    
    templates = get_templates(email)
    
    # If templates are empty, return a default message
    if not templates or len(templates) == 0:
        return ["Default template not found. Please add a template."], False
    
    # Process templates to ensure proper newlines
    processed_templates = [t.replace('\\r\\n', '\n').replace('\\n', '\n') for t in templates]
    
    # If we have templates, assume they are custom if there's more than one
    # This maintains backward compatibility with the using_custom flag
    using_custom = len(processed_templates) > 1
    
    return processed_templates, using_custom

def save_templates(templates):
    """
    Save templates to the database.
    This function is kept for compatibility but simply calls add_template for each template.
    """
    from flask import session
    email = session.get('user_email')
    
    if not email:
        logger.warning("No user email found in session, cannot save templates")
        return False
    
    # Clear existing templates (except default ones) and add new ones
    try:
        for template in templates:
            save_template(email, template, is_default=False)
        return True
    except Exception as e:
        logger.error(f"Error saving templates: {e}")
        return False

def add_template(template_text):
    """
    Add a new template to the database.
    """
    try:
        from flask import session
        email = session.get('user_email')
        
        if not email:
            return False, "User not logged in"
        
        templates = get_templates(email)
        if len(templates) >= 5:
            return False, "Maximum 5 templates allowed"
        
        success = save_template(email, template_text, is_default=False)
        if success:
            return True, "Template added successfully"
        else:
            return False, "Failed to save template"
    except Exception as e:
        logger.error(f"Error adding template: {e}")
        return False, str(e)

def delete_template(template_id):
    """
    Delete a template from the database.
    """
    try:
        from flask import session
        email = session.get('user_email')
        
        if not email:
            return False, "User not logged in"
        
        templates = get_templates(email)
        
        # Convert template_id to integer
        template_id = int(template_id)
        
        # Ensure template_id is valid
        if template_id < 0 or template_id >= len(templates):
            return False, "Template not found"
        
        # In the database context, we need the actual template ID
        # Since we don't have it, we'll need to get the template text and use that
        template_to_delete = templates[template_id]
        
        # For now, we'll simulate this by re-adding all templates except the one we want to delete
        remaining_templates = [t for i, t in enumerate(templates) if i != template_id]
        
        # If we have no templates left, ensure we keep at least one default template
        if len(remaining_templates) == 0:
            return False, "Cannot delete the last template. At least one template must remain."
        
        # Delete the template from the database using the index
        from db.templates import delete_template as db_delete_template
        success = db_delete_template(email, template_id)
        
        if success:
            return True, "Template deleted successfully"
        else:
            return False, "Failed to delete template"
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        return False, str(e)
