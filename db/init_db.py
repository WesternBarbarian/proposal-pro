
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
        
        # Create users table with user_role ENUM
        create_user_role_enum = """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                CREATE TYPE user_role AS ENUM ('SUPER_ADMIN','TENANT_ADMIN', 'STANDARD_USER');
            END IF;
        END$$;
        """
        
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
          id               UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id        UUID      NOT NULL REFERENCES tenants(id),
          email            TEXT      NOT NULL,
          name             TEXT,
          role             user_role NOT NULL DEFAULT 'STANDARD_USER',
          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        
        -- ensure no two users share the same email within a tenant:
        CREATE UNIQUE INDEX IF NOT EXISTS ux_users_tenant_email ON users(tenant_id, email);
        CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id);
        """

        # Create price_lists table for tenant-specific price lists
        create_price_lists_table = """
        CREATE TABLE IF NOT EXISTS price_lists (
          id               UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id        UUID      NOT NULL REFERENCES tenants(id),
          prices           JSONB     NOT NULL,
          created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- Create index on tenant_id for faster lookups
        CREATE INDEX IF NOT EXISTS idx_price_lists_tenant_id ON price_lists(tenant_id);
        """

        
        # First create the ENUM type if it doesn't exist
        execute_query(create_user_role_enum, fetch=False)
        # Then create the users table
        execute_query(create_users_table, fetch=False)
        logger.info("Users table created successfully")

        # Create the price_lists table
        execute_query(create_price_lists_table, fetch=False)
        logger.info("Price lists table created successfully")


        
        
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
