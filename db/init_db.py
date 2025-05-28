# Initialize drive settings table
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

        # Create templates table for tenant-specific templates
        create_templates_table = """
        CREATE TABLE IF NOT EXISTS templates (
          id               UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id        UUID      NOT NULL REFERENCES tenants(id),
          template_text    TEXT      NOT NULL,
          is_default      BOOLEAN   NOT NULL DEFAULT false,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- Create index on tenant_id for faster lookups
        CREATE INDEX IF NOT EXISTS idx_templates_tenant_id ON templates(tenant_id);
        """

        execute_query(create_templates_table, fetch=False)
        logger.info("Templates table created successfully")

        # Create estimates table for storing estimates data
        create_estimates_table = """
        CREATE TABLE IF NOT EXISTS estimates (
          estimate_id          UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id            UUID      NOT NULL REFERENCES tenants(id),
          customer_data        JSONB     NOT NULL,
          project_details      JSONB     NOT NULL,
          line_items           JSONB     NOT NULL,
          total_cost           DECIMAL(10,2) NOT NULL,
          created_by_email     TEXT      NOT NULL,
          created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at           TIMESTAMPTZ,              -- soft-delete flag
          proposal_id          UUID                      -- future reference to proposals table
        );

        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_estimates_tenant_id ON estimates(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_estimates_created_by ON estimates(created_by_email);
        CREATE INDEX IF NOT EXISTS idx_estimates_created_at ON estimates(created_at);
        CREATE INDEX IF NOT EXISTS idx_estimates_proposal_id ON estimates(proposal_id);
        """

        execute_query(create_estimates_table, fetch=False)
        logger.info("Estimates table created successfully")

        # Create proposals table for future use
        create_proposals_table = """
        CREATE TABLE IF NOT EXISTS proposals (
          proposal_id          UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id            UUID      NOT NULL REFERENCES tenants(id),
          estimate_id          UUID      REFERENCES estimates(estimate_id),
          proposal_content     TEXT      NOT NULL,
          status               VARCHAR(50) NOT NULL DEFAULT 'draft',
          created_by_email     TEXT      NOT NULL,
          created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at           TIMESTAMPTZ               -- soft-delete flag
        );

        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_proposals_tenant_id ON proposals(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_proposals_estimate_id ON proposals(estimate_id);
        CREATE INDEX IF NOT EXISTS idx_proposals_created_by ON proposals(created_by_email);
        CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
        """

        execute_query(create_proposals_table, fetch=False)
        logger.info("Proposals table created successfully")

        # Create prompts table with version control
        create_prompts_table = """
        CREATE TABLE IF NOT EXISTS prompts (
          id                   UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id            UUID      NOT NULL REFERENCES tenants(id),
          name                 TEXT      NOT NULL,
          description          TEXT,
          system_instruction   TEXT,
          user_prompt          TEXT      NOT NULL,
          version              INTEGER   NOT NULL DEFAULT 1,
          is_active            BOOLEAN   NOT NULL DEFAULT true,
          created_by_email     TEXT      NOT NULL,
          created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          deleted_at           TIMESTAMPTZ               -- soft-delete flag
        );

        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS idx_prompts_tenant_id ON prompts(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_prompts_name ON prompts(name);
        CREATE INDEX IF NOT EXISTS idx_prompts_active ON prompts(is_active);
        CREATE UNIQUE INDEX IF NOT EXISTS ux_prompts_tenant_name_active ON prompts(tenant_id, name) WHERE is_active = true;
        """

        execute_query(create_prompts_table, fetch=False)
        logger.info("Prompts table created successfully")

        # Create drive_settings table
        create_drive_settings_table = """
        CREATE TABLE IF NOT EXISTS drive_settings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(id),
            setting_type VARCHAR(50) NOT NULL,
            setting_key VARCHAR(100) NOT NULL,
            setting_value TEXT NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by_email VARCHAR(255) NOT NULL,
            UNIQUE(tenant_id, setting_type, setting_key)
        );
        """

        execute_query(create_drive_settings_table, fetch=False)
        logger.info("Drive settings table created successfully")

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