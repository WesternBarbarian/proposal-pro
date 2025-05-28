
import logging
from db.connection import execute_query

logger = logging.getLogger(__name__)

def create_drive_settings_table():
    """Create the drive_settings table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS drive_settings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID REFERENCES tenants(id),
        setting_type VARCHAR(50) NOT NULL, -- 'folder_template', 'root_folder', 'auto_organize'
        setting_key VARCHAR(100) NOT NULL,
        setting_value TEXT NOT NULL,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by_email VARCHAR(255) NOT NULL,
        UNIQUE(tenant_id, setting_type, setting_key)
    );
    """
    execute_query(query, fetch=False)
    logger.info("Drive settings table created successfully")

def get_drive_setting(tenant_id, setting_type, setting_key, default_value=None):
    """Get a drive setting for a tenant."""
    query = """
    SELECT setting_value FROM drive_settings 
    WHERE tenant_id = %s AND setting_type = %s AND setting_key = %s AND is_active = true;
    """
    result = execute_query(query, (tenant_id, setting_type, setting_key))
    
    if result and len(result) > 0:
        return result[0]['setting_value']
    return default_value

def set_drive_setting(tenant_id, setting_type, setting_key, setting_value, created_by_email):
    """Set a drive setting for a tenant."""
    query = """
    INSERT INTO drive_settings (tenant_id, setting_type, setting_key, setting_value, created_by_email)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (tenant_id, setting_type, setting_key)
    DO UPDATE SET 
        setting_value = EXCLUDED.setting_value,
        updated_at = CURRENT_TIMESTAMP,
        created_by_email = EXCLUDED.created_by_email;
    """
    execute_query(query, (tenant_id, setting_type, setting_key, setting_value, created_by_email), fetch=False)

def get_folder_template(tenant_id):
    """Get the folder naming template for a tenant."""
    return get_drive_setting(tenant_id, 'folder_template', 'root_folder', 'Project Proposals')

def get_auto_organize_setting(tenant_id):
    """Check if auto-organization is enabled."""
    setting = get_drive_setting(tenant_id, 'auto_organize', 'enabled', 'false')
    return setting.lower() == 'true'

def get_subfolder_template(tenant_id):
    """Get subfolder organization template."""
    return get_drive_setting(tenant_id, 'folder_template', 'subfolder_pattern', '{client_name}')
