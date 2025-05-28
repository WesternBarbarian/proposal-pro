import logging
from db.connection import execute_query

# Configure logging
logger = logging.getLogger(__name__)

def is_admin_user(email):
    """Check if a user has admin privileges"""
    if not email:
        return False

    try:
        query = """
        SELECT role FROM users 
        WHERE email = %s AND deleted_at IS NULL;
        """
        result = execute_query(query, (email,))

        if result and len(result) > 0:
            role = result[0]['role']
            return role in ['SUPER_ADMIN', 'TENANT_ADMIN']

        return False
    except Exception as e:
        logger.error(f"Error checking admin status for {email}: {e}")
        return False

def get_tenant_id_by_user_email(email):
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

def update_allowed_users_from_db():
    """
    Get all tenants with plan_level 'super' or 'basic'
    """
    try:
        query = """
        SELECT users.email 
        FROM users JOIN tenants ON users.tenant_id = tenants.id 
        WHERE tenants.plan_level IN ('super', 'basic')
        AND users.deleted_at IS NULL;
        """

        result = execute_query(query)
        if result:
            return [tenant['email'] for tenant in result if tenant.get('email')]
        return []
    except Exception as e:
        logger.error(f"Error retrieving allowed tenants: {e}")
        return []