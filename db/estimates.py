
import logging
import json
from datetime import datetime
from db.connection import execute_query
from db.tenants import get_tenant_id_by_user_email

logger = logging.getLogger(__name__)

def create_estimate(user_email, customer, project_details, line_items, total_cost):
    """
    Create a new estimate in the database
    
    Args:
        user_email (str): Email of the user creating the estimate
        customer (dict): Customer information
        project_details (dict): Project details
        line_items (dict): Line items with pricing
        total_cost (float): Total cost of the estimate
        
    Returns:
        str: Estimate ID if successful, None if failed
    """
    try:
        # Get tenant ID from user email
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user email: {user_email}")
            return None
        
        # Create the estimate
        query = """
        INSERT INTO estimates (tenant_id, customer_data, project_details, line_items, total_cost, created_by_email)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING estimate_id
        """
        
        params = (
            tenant_id,
            json.dumps(customer),
            json.dumps(project_details),
            json.dumps(line_items),
            total_cost,
            user_email
        )
        
        result = execute_query(query, params, fetch=True)
        if result and len(result) > 0:
            estimate_id = result[0]['estimate_id']
            logger.info(f"Created estimate with ID: {estimate_id}")
            return str(estimate_id)
        
        return None
        
    except Exception as e:
        logger.error(f"Error creating estimate: {e}")
        return None

def get_estimate(estimate_id, user_email):
    """
    Get an estimate by ID, ensuring it belongs to the user's tenant
    
    Args:
        estimate_id (str): The estimate ID
        user_email (str): Email of the user requesting the estimate
        
    Returns:
        dict: Estimate data if found and authorized, None otherwise
    """
    try:
        # Get tenant ID from user email
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user email: {user_email}")
            return None
        
        query = """
        SELECT estimate_id, customer_data, project_details, line_items, total_cost, 
               created_at, updated_at, created_by_email
        FROM estimates 
        WHERE estimate_id = %s AND tenant_id = %s AND deleted_at IS NULL
        """
        
        result = execute_query(query, (estimate_id, tenant_id), fetch=True)
        
        if result and len(result) > 0:
            estimate = result[0]
            return {
                'estimate_id': str(estimate['estimate_id']),
                'customer': json.loads(estimate['customer_data']),
                'project_details': json.loads(estimate['project_details']),
                'line_items': json.loads(estimate['line_items']),
                'total_cost': float(estimate['total_cost']),
                'created_at': estimate['created_at'],
                'updated_at': estimate['updated_at'],
                'created_by_email': estimate['created_by_email']
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting estimate {estimate_id}: {e}")
        return None

def update_estimate(estimate_id, user_email, customer=None, project_details=None, line_items=None, total_cost=None):
    """
    Update an existing estimate
    
    Args:
        estimate_id (str): The estimate ID
        user_email (str): Email of the user updating the estimate
        customer (dict, optional): Updated customer information
        project_details (dict, optional): Updated project details
        line_items (dict, optional): Updated line items
        total_cost (float, optional): Updated total cost
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get tenant ID from user email
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user email: {user_email}")
            return False
        
        # Build dynamic update query based on provided parameters
        update_fields = []
        params = []
        
        if customer is not None:
            update_fields.append("customer_data = %s")
            params.append(json.dumps(customer))
            
        if project_details is not None:
            update_fields.append("project_details = %s")
            params.append(json.dumps(project_details))
            
        if line_items is not None:
            update_fields.append("line_items = %s")
            params.append(json.dumps(line_items))
            
        if total_cost is not None:
            update_fields.append("total_cost = %s")
            params.append(total_cost)
        
        if not update_fields:
            logger.warning("No fields to update")
            return False
        
        update_fields.append("updated_at = %s")
        params.append(datetime.utcnow())
        
        # Add WHERE clause parameters
        params.extend([estimate_id, tenant_id])
        
        query = f"""
        UPDATE estimates 
        SET {', '.join(update_fields)}
        WHERE estimate_id = %s AND tenant_id = %s AND deleted_at IS NULL
        """
        
        execute_query(query, params, fetch=False)
        logger.info(f"Updated estimate {estimate_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating estimate {estimate_id}: {e}")
        return False

def get_estimates_for_tenant(user_email, limit=50, offset=0):
    """
    Get all estimates for a tenant
    
    Args:
        user_email (str): Email of the user requesting estimates
        limit (int): Maximum number of estimates to return
        offset (int): Number of estimates to skip
        
    Returns:
        list: List of estimates for the tenant
    """
    try:
        # Get tenant ID from user email
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user email: {user_email}")
            return []
        
        query = """
        SELECT estimate_id, customer_data, project_details, line_items, total_cost, 
               created_at, updated_at, created_by_email
        FROM estimates 
        WHERE tenant_id = %s AND deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """
        
        result = execute_query(query, (tenant_id, limit, offset), fetch=True)
        
        estimates = []
        for row in result:
            estimates.append({
                'estimate_id': str(row['estimate_id']),
                'customer': json.loads(row['customer_data']),
                'project_details': json.loads(row['project_details']),
                'line_items': json.loads(row['line_items']),
                'total_cost': float(row['total_cost']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at'],
                'created_by_email': row['created_by_email']
            })
        
        return estimates
        
    except Exception as e:
        logger.error(f"Error getting estimates for tenant: {e}")
        return []

def delete_estimate(estimate_id, user_email):
    """
    Soft delete an estimate
    
    Args:
        estimate_id (str): The estimate ID
        user_email (str): Email of the user deleting the estimate
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get tenant ID from user email
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user email: {user_email}")
            return False
        
        query = """
        UPDATE estimates 
        SET deleted_at = %s, updated_at = %s
        WHERE estimate_id = %s AND tenant_id = %s AND deleted_at IS NULL
        """
        
        now = datetime.utcnow()
        execute_query(query, (now, now, estimate_id, tenant_id), fetch=False)
        logger.info(f"Deleted estimate {estimate_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting estimate {estimate_id}: {e}")
        return False
