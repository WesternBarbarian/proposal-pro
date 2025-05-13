
import logging
from db.connection import execute_query

# Configure logging
logger = logging.getLogger(__name__)

def get_allowed_domains():
    """
    Get all domain names from tenants with plan_level 'super' or 'basic'
    """
    try:
        query = """
        SELECT name, billing_email FROM tenants 
        WHERE plan_level IN ('super', 'basic') 
        AND deleted_at IS NULL
        """
        
        result = execute_query(query)
        domains = []
        if result:
            for tenant in result:
                # Extract domain from billing email if available
                if tenant.get('billing_email'):
                    domain = tenant['billing_email'].split('@')[-1]
                    if domain and '.' in domain:
                        domains.append(domain)
        return domains
    except Exception as e:
        logger.error(f"Error retrieving allowed domains: {e}")
        return []

def get_allowed_tenants():
    """
    Legacy function - kept for compatibility
    Get all tenants with plan_level 'super' or 'basic'
    """
    try:
        query = """
        SELECT name, billing_email FROM tenants 
        WHERE plan_level IN ('super', 'basic') 
        AND deleted_at IS NULL
        """
        
        result = execute_query(query)
        if result:
            return [tenant['billing_email'] for tenant in result if tenant.get('billing_email')]
        return []
    except Exception as e:
        logger.error(f"Error retrieving allowed tenants: {e}")
        return []
