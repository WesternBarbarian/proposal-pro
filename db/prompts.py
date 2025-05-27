
import logging
from typing import Dict, List, Optional, Any
from db.connection import execute_query

# Configure module logger
logger = logging.getLogger(__name__)

def get_active_prompts(tenant_id: str) -> List[Dict[str, Any]]:
    """Get all active prompts for a tenant"""
    query = """
    SELECT id, name, description, system_instruction, user_prompt, version, created_by_email, created_at, updated_at
    FROM prompts 
    WHERE tenant_id = %s AND is_active = true AND deleted_at IS NULL
    ORDER BY name, version DESC
    """
    return execute_query(query, (tenant_id,))

def get_prompt_by_name(tenant_id: str, name: str) -> Optional[Dict[str, Any]]:
    """Get the active version of a prompt by name"""
    query = """
    SELECT id, name, description, system_instruction, user_prompt, version, created_by_email, created_at, updated_at
    FROM prompts 
    WHERE tenant_id = %s AND name = %s AND is_active = true AND deleted_at IS NULL
    """
    results = execute_query(query, (tenant_id, name))
    return results[0] if results else None

def get_prompt_versions(tenant_id: str, name: str) -> List[Dict[str, Any]]:
    """Get all versions of a prompt"""
    query = """
    SELECT id, name, description, system_instruction, user_prompt, version, is_active, created_by_email, created_at, updated_at
    FROM prompts 
    WHERE tenant_id = %s AND name = %s AND deleted_at IS NULL
    ORDER BY version DESC
    """
    return execute_query(query, (tenant_id, name))

def create_prompt(tenant_id: str, name: str, description: str, system_instruction: str, 
                 user_prompt: str, created_by_email: str) -> str:
    """Create a new prompt or new version of existing prompt"""
    logger.debug(f"Creating prompt '{name}' for tenant {tenant_id}")
    
    try:
        # Check if prompt already exists
        existing = get_prompt_by_name(tenant_id, name)
        logger.debug(f"Existing prompt check for '{name}': {existing is not None}")
        
        if existing:
            # Deactivate current version
            deactivate_query = """
            UPDATE prompts SET is_active = false, updated_at = now()
            WHERE tenant_id = %s AND name = %s AND is_active = true
            """
            execute_query(deactivate_query, (tenant_id, name), fetch=False)
            logger.debug(f"Deactivated existing version of prompt '{name}'")
            
            # Get next version number
            version_query = """
            SELECT COALESCE(MAX(version), 0) + 1 as next_version
            FROM prompts WHERE tenant_id = %s AND name = %s
            """
            version_result = execute_query(version_query, (tenant_id, name))
            next_version = version_result[0]['next_version']
            logger.debug(f"Next version for prompt '{name}': {next_version}")
        else:
            next_version = 1
            logger.debug(f"Creating new prompt '{name}' with version 1")
        
        # Insert new version
        insert_query = """
        INSERT INTO prompts (tenant_id, name, description, system_instruction, user_prompt, version, created_by_email)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        logger.debug(f"Inserting prompt with data: name='{name}', version={next_version}")
        result = execute_query(insert_query, (tenant_id, name, description, system_instruction, user_prompt, next_version, created_by_email))
        
        if result and len(result) > 0:
            prompt_id = result[0]['id']
            logger.info(f"Successfully created prompt '{name}' with ID: {prompt_id}")
            return prompt_id
        else:
            logger.error(f"Failed to create prompt '{name}' - no result returned from insert")
            raise Exception("No result returned from prompt insert")
            
    except Exception as e:
        logger.error(f"Error creating prompt '{name}': {str(e)}")
        logger.exception("Full error details:")
        raise

def rollback_prompt(tenant_id: str, name: str, target_version: int, updated_by_email: str) -> bool:
    """Rollback a prompt to a specific version"""
    # Get the target version
    target_query = """
    SELECT id, description, system_instruction, user_prompt
    FROM prompts 
    WHERE tenant_id = %s AND name = %s AND version = %s AND deleted_at IS NULL
    """
    target_results = execute_query(target_query, (tenant_id, name, target_version))
    
    if not target_results:
        return False
    
    target = target_results[0]
    
    # Deactivate current version
    deactivate_query = """
    UPDATE prompts SET is_active = false, updated_at = now()
    WHERE tenant_id = %s AND name = %s AND is_active = true
    """
    execute_query(deactivate_query, (tenant_id, name), fetch=False)
    
    # Create new version based on target
    create_prompt(tenant_id, name, target['description'], target['system_instruction'], 
                 target['user_prompt'], updated_by_email)
    
    return True

def delete_prompt(tenant_id: str, name: str) -> bool:
    """Soft delete a prompt (all versions)"""
    query = """
    UPDATE prompts SET deleted_at = now(), is_active = false, updated_at = now()
    WHERE tenant_id = %s AND name = %s AND deleted_at IS NULL
    """
    execute_query(query, (tenant_id, name), fetch=False)
    return True

def migrate_prompt_from_file(tenant_id: str, prompt_data: Dict[str, Any], created_by_email: str) -> str:
    """Migrate a prompt from file format to database"""
    logger.debug(f"Migrating prompt data: {prompt_data}")
    logger.debug(f"Tenant ID: {tenant_id}, Created by: {created_by_email}")
    
    try:
        prompt_id = create_prompt(
            tenant_id=tenant_id,
            name=prompt_data.get('name', ''),
            description=prompt_data.get('description', ''),
            system_instruction=prompt_data.get('system_instruction', ''),
            user_prompt=prompt_data.get('user_prompt', ''),
            created_by_email=created_by_email
        )
        logger.info(f"Successfully migrated prompt '{prompt_data.get('name', '')}' with ID: {prompt_id}")
        return prompt_id
    except Exception as e:
        logger.error(f"Error migrating prompt '{prompt_data.get('name', '')}': {str(e)}")
        logger.exception("Full migration error details:")
        raise
