
#!/usr/bin/env python3
"""
Debug script to check prompts in the database
"""

import logging
from db.connection import execute_query

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_prompts():
    """Check what prompts exist in the database"""
    try:
        # Get all tenants
        tenants_query = "SELECT id, name FROM tenants WHERE deleted_at IS NULL;"
        tenants = execute_query(tenants_query)
        logger.info(f"Found {len(tenants)} tenants:")
        for tenant in tenants:
            logger.info(f"  - {tenant['name']} (ID: {tenant['id']})")
        
        # Get all prompts across all tenants
        prompts_query = """
        SELECT t.name as tenant_name, p.name, p.description, p.version, p.is_active, p.created_at, p.created_by_email
        FROM prompts p 
        JOIN tenants t ON p.tenant_id = t.id 
        WHERE p.deleted_at IS NULL 
        ORDER BY t.name, p.name, p.version DESC;
        """
        prompts = execute_query(prompts_query)
        logger.info(f"Found {len(prompts)} prompts in database:")
        
        if prompts:
            for prompt in prompts:
                logger.info(f"  - Tenant: {prompt['tenant_name']}, Name: {prompt['name']}, Version: {prompt['version']}, Active: {prompt['is_active']}, Created: {prompt['created_at']}")
        else:
            logger.warning("No prompts found in database!")
            
        # Check prompts table structure
        table_query = """
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'prompts' 
        ORDER BY ordinal_position;
        """
        columns = execute_query(table_query)
        logger.info("Prompts table structure:")
        for col in columns:
            logger.info(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
            
    except Exception as e:
        logger.error(f"Error checking prompts: {str(e)}")
        logger.exception("Full error details:")

if __name__ == "__main__":
    check_prompts()
