
import json
import logging
import os
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

        # If no templates exist, initialize default templates for this tenant
        logger.info(f"No templates found for tenant {tenant_id}, initializing default templates")
        initialize_templates_for_tenant(tenant_id)
        
        # Try again to get templates
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

def delete_template(email, template_index):
    """Delete a template for a user's tenant by index."""
    try:
        tenant_id = get_tenant_id_for_user(email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {email}")
            return False

        # Get all templates for the tenant
        query_get = """
        SELECT id, template_text, is_default FROM templates 
        WHERE tenant_id = %s
        ORDER BY created_at;
        """
        templates = execute_query(query_get, (tenant_id,))
        
        if not templates or template_index >= len(templates):
            logger.error(f"Template index {template_index} not found")
            return False
            
        template_to_delete = templates[template_index]
        
        # Don't allow deletion of default templates
        if template_to_delete['is_default']:
            logger.error(f"Cannot delete default template")
            return False

        # Delete the template by its actual UUID
        query_delete = """
        DELETE FROM templates 
        WHERE tenant_id = %s 
        AND id = %s;
        """
        execute_query(query_delete, (tenant_id, template_to_delete['id']), fetch=False)
        
        # Check if there are any remaining templates
        remaining_query = """
        SELECT COUNT(*) as count FROM templates 
        WHERE tenant_id = %s;
        """
        remaining_result = execute_query(remaining_query, (tenant_id,))
        
        # If no templates remain, initialize default templates
        if remaining_result and remaining_result[0]['count'] == 0:
            logger.info(f"No templates remaining for tenant {tenant_id}, initializing default templates")
            initialize_templates_for_tenant(tenant_id)
        
        return True
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        return False

def initialize_templates_for_tenant(tenant_id):
    """Initialize default templates for a specific tenant."""
    try:
        # Load default templates
        default_templates = []
        try:
            with open('default_template.json', 'r') as f:
                template_data = json.load(f)
                if 'templates' in template_data and isinstance(template_data['templates'], list):
                    default_templates = template_data['templates']
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading default templates: {e}")
            default_templates = ["Default template not found. Please add a template."]
        
        # Add default templates for this tenant
        for template in default_templates:
            query_insert = """
            INSERT INTO templates (tenant_id, template_text, is_default) 
            VALUES (%s, %s, true);
            """
            execute_query(query_insert, (tenant_id, template), fetch=False)
            
        logger.info(f"Initialized {len(default_templates)} default templates for tenant {tenant_id}")
        return True
    except Exception as e:
        logger.error(f"Error initializing templates for tenant {tenant_id}: {e}")
        return False

def initialize_templates():
    """Migrate existing template files to database."""
    try:
        # Import app within function to avoid circular imports
        from app import app
        
        # Load default templates
        default_templates = []
        try:
            with open('default_template.json', 'r') as f:
                logger.info("Reading default_template.json")
                template_data = json.load(f)
                logger.info(f"Template data loaded: {template_data}")
                if 'templates' in template_data and isinstance(template_data['templates'], list):
                    default_templates = template_data['templates']
                    logger.info(f"Default templates found: {len(default_templates)}")
                else:
                    logger.error("Invalid template format in default_template.json")
        except FileNotFoundError:
            logger.error("default_template.json file not found")
            default_templates = ["Default template not found. Please add a template."]
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing default_template.json: {e}")
            default_templates = ["Error parsing template file. Please check format."]
        
        # Try to load custom templates
        custom_templates = {}
        try:
            if os.path.exists('custom_templates.json'):
                with open('custom_templates.json', 'r') as f:
                    logger.info("Reading custom_templates.json")
                    custom_data = json.load(f)
                    # Handle different formats of custom templates
                    if 'templates' in custom_data:
                        if isinstance(custom_data['templates'], dict):
                            # Format: {"templates": {"tenant_id": [templates]}}
                            custom_templates = custom_data['templates']
                        elif isinstance(custom_data['templates'], list):
                            # Format: {"templates": [templates]} - no tenant association
                            logger.info("Custom templates found but not tenant-specific")
                    logger.info(f"Custom templates found for {len(custom_templates)} tenants")
        except Exception as e:
            logger.error(f"Error loading custom templates: {e}")
        
        with app.app_context():
            # Get all tenants
            query = "SELECT id FROM tenants WHERE deleted_at IS NULL;"
            tenants = execute_query(query)
            logger.info(f"Found {len(tenants)} tenants to initialize templates for")
            
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
                        logger.info(f"Adding default template for tenant {tenant_id}: {template[:30]}...")
                        query_insert = """
                        INSERT INTO templates (tenant_id, template_text, is_default) 
                        VALUES (%s, %s, true);
                        """
                        execute_query(query_insert, (tenant_id, template), fetch=False)
                    
                    # Add custom templates if they exist for this tenant
                    if tenant_id in custom_templates:
                        for template in custom_templates[tenant_id]:
                            logger.info(f"Adding custom template for tenant {tenant_id}")
                            query_insert = """
                            INSERT INTO templates (tenant_id, template_text, is_default) 
                            VALUES (%s, %s, false);
                            """
                            execute_query(query_insert, (tenant_id, template), fetch=False)
                    
                    # Verify templates were added
                    verify_query = "SELECT COUNT(*) as count FROM templates WHERE tenant_id = %s;"
                    verify_result = execute_query(verify_query, (tenant_id,))
                    if verify_result and verify_result[0]['count'] > 0:
                        logger.info(f"Successfully added {verify_result[0]['count']} templates for tenant {tenant_id}")
                    else:
                        logger.warning(f"Failed to verify templates for tenant {tenant_id}")
                else:
                    logger.info(f"Templates already exist for tenant {tenant_id}, skipping")
            
        return True
    except Exception as e:
        logger.error(f"Error initializing templates: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
