
import logging
from db.connection import execute_query

# Configure logging
logger = logging.getLogger(__name__)

def get_allowed_tenants():
    """
    Get all tenants with plan_level 'super' or 'basic'
    """
    try:
        query = """
        SELECT name, email FROM tenants 
        WHERE plan_level IN ('super', 'basic') 
        AND deleted_at IS NULL
        """
        
        result = execute_query(query)
        if result:
            return [tenant['email'] for tenant in result if tenant.get('email')]
        return []
    except Exception as e:
        logger.error(f"Error retrieving allowed tenants: {e}")
        return []
