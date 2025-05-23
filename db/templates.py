
import json
import logging
from db.connection import execute_query

# Configure logging
logger = logging.getLogger(__name__)

def get_tenant_id_for_user(email):
    """Get tenant ID for a given user email."""
    try:
        query = """
        SELECT tenant_id FROM users 
        WHERE email = %s
        AND deleted_at IS NULL;
        """
        result = execute_query(query, (email,))

        if result and len(result) > 0:
            return result[0]['tenant_id']
        return None
    except Exception as e:
        logger.error(f"Error getting tenant ID for user: {e}")
        return None

def get_templates(email):
    """Get templates for a user's tenant."""
    try:
        tenant_id = get_tenant_id_for_user(email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {email}")
            return []

        query = """
        SELECT template_text FROM templates 
        WHERE tenant_id = %s
        ORDER BY created_at;
        """
        result = execute_query(query, (tenant_id,))

        if result and len(result) > 0:
            return [row['template_text'] for row in result]

        return []
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return []

def save_template(email, template_text, is_default=False):
    """Save a new template for a user's tenant."""
    try:
        tenant_id = get_tenant_id_for_user(email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {email}")
            return False

        query = """
        INSERT INTO templates (tenant_id, template_text, is_default) 
        VALUES (%s, %s, %s);
        """
        execute_query(query, (tenant_id, template_text, is_default), fetch=False)
        return True
    except Exception as e:
        logger.error(f"Error saving template: {e}")
        return False

def delete_template(email, template_id):
    """Delete a template for a user's tenant."""
    try:
        tenant_id = get_tenant_id_for_user(email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {email}")
            return False

        query = """
        DELETE FROM templates 
        WHERE tenant_id = %s 
        AND id = %s 
        AND NOT is_default;
        """
        execute_query(query, (tenant_id, template_id), fetch=False)
        return True
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        return False

def initialize_templates():
    """Migrate existing template files to database."""
    try:
        from app import app
        with app.app_context():
            # Get all tenants
            query = "SELECT id FROM tenants WHERE deleted_at IS NULL;"
            tenants = execute_query(query)

        # Load default templates
        try:
            with open('default_template.json', 'r') as f:
                default_templates = json.load(f)['templates']
        except (FileNotFoundError, json.JSONDecodeError):
            default_templates = ["Default template not found. Please add a template."]

        # Try to load custom templates
        custom_templates = {}
        try:
            with open('custom_templates.json', 'r') as f:
                custom_data = json.load(f)
                for tenant_id in custom_data.get('templates', {}).keys():
                    custom_templates[tenant_id] = custom_data['templates'][tenant_id]
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # For each tenant, initialize templates
        for tenant in tenants:
            tenant_id = tenant['id']

            # Check if tenant already has templates
            query_check = "SELECT id FROM templates WHERE tenant_id = %s;"
            result = execute_query(query_check, (tenant_id,))

            if not result:
                logger.info(f"No templates found for tenant {tenant_id}, adding default templates")
                # Add default templates
                for template in default_templates:
                    query_insert = """
                    INSERT INTO templates (tenant_id, template_text, is_default) 
                    VALUES (%s, %s, true);
                    """
                    execute_query(query_insert, (tenant_id, template), fetch=False)
                    logger.info(f"Added default template for tenant {tenant_id}")

                # Add custom templates if they exist for this tenant
                if tenant_id in custom_templates:
                    for template in custom_templates[tenant_id]:
                        query_insert = """
                        INSERT INTO templates (tenant_id, template_text, is_default) 
                        VALUES (%s, %s, false);
                        """
                        execute_query(query_insert, (tenant_id, template), fetch=False)

                logger.info(f"Initialized templates for tenant {tenant_id}")

        return True
    except Exception as e:
        logger.error(f"Error initializing templates: {e}")
        return False
