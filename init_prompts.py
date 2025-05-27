
import logging
import os
from flask import Flask
from prompt_manager import get_prompt_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_prompts():
    """Initialize prompts in the database"""
    try:
        # Create a minimal Flask app context for database operations
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'temp-key-for-init'
        
        # Import database modules to ensure they're available
        from db.connection import execute_query
        from db.tenants import get_tenant_id_by_user_email
        
        with app.app_context():
            # Check if any tenants exist, create default if none
            tenants_result = execute_query("SELECT id FROM tenants WHERE deleted_at IS NULL LIMIT 1;")
            
            if not tenants_result:
                # Create a default tenant
                logger.info("No tenants found, creating default tenant...")
                create_tenant_query = """
                INSERT INTO tenants (name, plan_level, subscription_start, subscription_end, billing_email)
                VALUES ('Default Tenant', 'basic', CURRENT_DATE, CURRENT_DATE + INTERVAL '1 year', 'admin@system.local')
                RETURNING id;
                """
                tenant_result = execute_query(create_tenant_query)
                tenant_id = tenant_result[0]['id']
                logger.info(f"Created default tenant with ID: {tenant_id}")
                
                # Create a default system user for this tenant
                create_user_query = """
                INSERT INTO users (tenant_id, email, name, role)
                VALUES (%s, 'system@migration.local', 'System Migration User', 'TENANT_ADMIN');
                """
                execute_query(create_user_query, (tenant_id,), fetch=False)
                logger.info("Created default system user")
            else:
                tenant_id = tenants_result[0]['id']
                logger.info(f"Using existing tenant with ID: {tenant_id}")
            
            # Now simulate a session context by manually setting up the migration
            prompt_manager = get_prompt_manager()
            
            # Check if prompts directory exists
            prompts_dir = "prompts"
            if not os.path.exists(prompts_dir):
                logger.warning(f"Prompts directory '{prompts_dir}' does not exist.")
                return True
            
            # Manually migrate each prompt file
            migrated_count = 0
            for filename in os.listdir(prompts_dir):
                if filename.endswith('.json'):
                    prompt_name = os.path.splitext(filename)[0]
                    try:
                        import json
                        with open(os.path.join(prompts_dir, filename), 'r') as f:
                            prompt_data = json.load(f)
                        
                        # Check if prompt already exists
                        from db.prompts import get_prompt_by_name, migrate_prompt_from_file
                        existing = get_prompt_by_name(tenant_id, prompt_name)
                        
                        if not existing:
                            migrate_prompt_from_file(tenant_id, prompt_data, 'system@migration.local')
                            migrated_count += 1
                            logger.info(f"Migrated prompt: {prompt_name}")
                        else:
                            logger.info(f"Prompt '{prompt_name}' already exists in database, skipping")
                            
                    except Exception as e:
                        logger.error(f"Error migrating prompt '{prompt_name}': {str(e)}")
            
            logger.info(f"Migration completed. Migrated {migrated_count} prompts")
            return True
            
    except Exception as e:
        logger.error(f"Error during prompt initialization: {str(e)}")
        return False

if __name__ == "__main__":
    success = init_prompts()
    if success:
        print("Prompts initialized successfully!")
    else:
        print("Failed to initialize prompts")
