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

def get_price_list(email):
    """Get price list for a user's tenant."""
    try:
        tenant_id = get_tenant_id_for_user(email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {email}")
            return {}

        query = """
        SELECT prices FROM price_lists 
        WHERE tenant_id = %s;
        """
        result = execute_query(query, (tenant_id,))

        if result and len(result) > 0:
            return result[0]['prices']

        # If no price list exists yet for this tenant, return empty dict
        return {}
    except Exception as e:
        logger.error(f"Error getting price list: {e}")
        return {}

def save_price_list(email, price_list):
    """Save or update price list for a user's tenant."""
    try:
        tenant_id = get_tenant_id_for_user(email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {email}")
            return False

        # Check if price list already exists for this tenant
        query_check = """
        SELECT id FROM price_lists 
        WHERE tenant_id = %s;
        """
        result = execute_query(query_check, (tenant_id,))

        if result and len(result) > 0:
            # Update existing price list
            query_update = """
            UPDATE price_lists 
            SET prices = %s, updated_at = now() 
            WHERE tenant_id = %s;
            """
            execute_query(query_update, (json.dumps(price_list), tenant_id), fetch=False)
        else:
            # Insert new price list
            query_insert = """
            INSERT INTO price_lists (tenant_id, prices) 
            VALUES (%s, %s);
            """
            execute_query(query_insert, (tenant_id, json.dumps(price_list)), fetch=False)

        return True
    except Exception as e:
        logger.error(f"Error saving price list: {e}")
        return False

def initialize_price_lists():
    """Migrate existing price_list.json to database if needed."""
    try:
        # Get all tenants
        query = "SELECT id FROM tenants WHERE deleted_at IS NULL;"
        tenants = execute_query(query)

        # Try to load the existing price_list.json
        try:
            with open('price_list.json', 'r') as f:
                default_prices = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            default_prices = {}

        # For each tenant, initialize a price list if they don't have one
        for tenant in tenants:
            tenant_id = tenant['id']

            # Check if tenant already has a price list
            query_check = "SELECT id FROM price_lists WHERE tenant_id = %s;"
            result = execute_query(query_check, (tenant_id,))

            if not result:
                # Initialize tenant with default price list
                query_insert = "INSERT INTO price_lists (tenant_id, prices) VALUES (%s, %s);"
                execute_query(query_insert, (tenant_id, json.dumps(default_prices)), fetch=False)
                logger.info(f"Initialized price list for tenant {tenant_id}")

        return True
    except Exception as e:
        logger.error(f"Error initializing price lists: {e}")
        return False
