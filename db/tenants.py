
import logging
from db.connection import execute_query

# Configure logging
logger = logging.getLogger(__name__)

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
