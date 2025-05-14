
import logging
from db.connection import execute_query

# Configure logging
logger = logging.getLogger(__name__)

def is_admin_user(email):
    """Check if a user is an admin user with session management permissions."""
    try:
        # Query database for admin users (users with role SUPER_ADMIN or TENANT_ADMIN)
        query = """
        SELECT email FROM users
        WHERE role IN ('SUPER_ADMIN', 'TENANT_ADMIN')
        AND deleted_at IS NULL;
        """
        result = execute_query(query)
        
        # Extract admin emails from result
        admin_emails = [user['email'] for user in result if user.get('email')]
        
        return email in admin_emails
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        # Return False on error instead of falling back to config
        return False

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
