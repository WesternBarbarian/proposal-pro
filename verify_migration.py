
#!/usr/bin/env python3
"""
Verification script to check if prompts were actually saved to the database
"""

import sys
import os
import logging
from flask import Flask

# Add current directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_migration():
    """Verify that prompts were actually saved to the database"""
    try:
        # Create a minimal Flask app context for database operations
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'test-key'
        
        with app.app_context():
            from db.connection import execute_query
            
            # Check if database connection works
            logger.info("Testing database connection...")
            result = execute_query("SELECT 1 as test;")
            if result:
                logger.info("✓ Database connection successful")
            else:
                logger.error("✗ Database connection failed")
                return False
            
            # Get all tenants
            tenants_query = "SELECT id, name FROM tenants WHERE deleted_at IS NULL;"
            tenants = execute_query(tenants_query)
            logger.info(f"Found {len(tenants)} tenants:")
            for tenant in tenants:
                logger.info(f"  - {tenant['name']} (ID: {tenant['id']})")
            
            if not tenants:
                logger.error("No tenants found!")
                return False
            
            # Check prompts for each tenant
            total_prompts = 0
            for tenant in tenants:
                tenant_id = tenant['id']
                prompts_query = """
                SELECT name, description, version, is_active, created_at, created_by_email
                FROM prompts 
                WHERE tenant_id = %s AND deleted_at IS NULL 
                ORDER BY name, version DESC;
                """
                prompts = execute_query(prompts_query, (tenant_id,))
                
                logger.info(f"\nTenant '{tenant['name']}' has {len(prompts)} prompts:")
                for prompt in prompts:
                    status = "ACTIVE" if prompt['is_active'] else "inactive"
                    logger.info(f"  - {prompt['name']} v{prompt['version']} ({status}) - {prompt['created_at']}")
                
                total_prompts += len(prompts)
            
            logger.info(f"\n✓ Total prompts in database: {total_prompts}")
            
            # Check prompt files in directory
            prompts_dir = "prompts"
            file_count = 0
            if os.path.exists(prompts_dir):
                for filename in os.listdir(prompts_dir):
                    if filename.endswith('.json'):
                        file_count += 1
                        logger.info(f"  Found prompt file: {filename}")
            
            logger.info(f"✓ Found {file_count} prompt files on disk")
            
            if total_prompts == 0 and file_count > 0:
                logger.error("✗ Migration appears to have failed - files exist but no prompts in database")
                return False
            elif total_prompts > 0:
                logger.info("✓ Migration appears successful")
                return True
            else:
                logger.warning("⚠ No prompts found in files or database")
                return True
                
    except Exception as e:
        logger.error(f"Error during verification: {str(e)}")
        logger.exception("Full verification error details:")
        return False

if __name__ == "__main__":
    success = verify_migration()
    sys.exit(0 if success else 1)
