
import logging
from db.connection import execute_query

# Configure logging
logger = logging.getLogger(__name__)

def create_tables():
    """
    Create all required database tables if they don't exist
    """
    try:
        # Create tenants table
        create_tenants_table = """
        CREATE TABLE IF NOT EXISTS tenants (
          id                     UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
          name                   TEXT      NOT NULL,
          plan_level             VARCHAR(50) NOT NULL,
          subscription_start     DATE      NOT NULL,
          subscription_end       DATE      NOT NULL,
          billing_email          TEXT,
          billing_address        TEXT,
          google_doc_template_id TEXT,      -- optional per-tenant Doc template
          created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at             TIMESTAMPTZ              -- soft-delete flag
        );
        """
        
        execute_query(create_tenants_table, fetch=False)
        logger.info("Tenants table created successfully")
        
        return True
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        return False

if __name__ == "__main__":
    # When run directly, create the tables
    # We need to import and use the Flask app context
    from app import app
    with app.app_context():
        success = create_tables()
        if success:
            print("Database tables created successfully")
        else:
            print("Failed to create database tables")
