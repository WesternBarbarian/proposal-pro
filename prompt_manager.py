
import os
import json
import logging
from typing import Dict, Any, Optional
from flask import session
from db.prompts import get_active_prompts, get_prompt_by_name, create_prompt, rollback_prompt, delete_prompt, migrate_prompt_from_file

# Configure module logger
logger = logging.getLogger(__name__)

class PromptManager:
    """Manages loading and retrieving prompts from database."""
    
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = prompts_dir
        self.prompts: Dict[str, Any] = {}
        # Migration will be handled separately
    
    def _get_tenant_id(self) -> Optional[str]:
        """Get current tenant ID from session"""
        # For now, return a default tenant ID if not in session
        # In production, this should come from the authenticated user session
        return session.get('tenant_id', '00000000-0000-0000-0000-000000000001')
    
    def _load_all_prompts(self) -> None:
        """Load all prompts from database for current tenant"""
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            logger.warning("No tenant ID available, cannot load prompts")
            return
            
        try:
            db_prompts = get_active_prompts(tenant_id)
            self.prompts = {}
            
            for prompt in db_prompts:
                self.prompts[prompt['name']] = {
                    'name': prompt['name'],
                    'description': prompt['description'],
                    'system_instruction': prompt['system_instruction'],
                    'user_prompt': prompt['user_prompt'],
                    'version': prompt['version'],
                    'created_by_email': prompt['created_by_email'],
                    'created_at': prompt['created_at'],
                    'updated_at': prompt['updated_at']
                }
                
            logger.debug(f"Loaded {len(self.prompts)} prompts from database")
            
        except Exception as e:
            logger.error(f"Error loading prompts from database: {str(e)}")
            # Fallback to file-based loading if database fails
            self._load_from_files()
    
    def _load_from_files(self) -> None:
        """Fallback method to load prompts from files"""
        if not os.path.exists(self.prompts_dir):
            logger.warning(f"Prompts directory '{self.prompts_dir}' does not exist.")
            return
        
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith('.json'):
                prompt_name = os.path.splitext(filename)[0]
                try:
                    with open(os.path.join(self.prompts_dir, filename), 'r') as f:
                        self.prompts[prompt_name] = json.load(f)
                        logger.debug(f"Loaded prompt from file: {prompt_name}")
                except Exception as e:
                    logger.error(f"Error loading prompt '{prompt_name}' from file: {str(e)}")
    
    def get_prompt(self, prompt_name: str) -> Optional[Any]:
        """Get a prompt by name."""
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            # Fallback to in-memory prompts
            return self.prompts.get(prompt_name)
            
        try:
            db_prompt = get_prompt_by_name(tenant_id, prompt_name)
            if db_prompt:
                return {
                    'name': db_prompt['name'],
                    'description': db_prompt['description'],
                    'system_instruction': db_prompt['system_instruction'],
                    'user_prompt': db_prompt['user_prompt'],
                    'version': db_prompt['version']
                }
        except Exception as e:
            logger.error(f"Error getting prompt '{prompt_name}' from database: {str(e)}")
            
        # Fallback to in-memory prompts
        return self.prompts.get(prompt_name)
    
    def get_system_instruction(self, prompt_name: str) -> Optional[str]:
        """Get the system instruction from a prompt."""
        prompt = self.get_prompt(prompt_name)
        if not prompt or 'system_instruction' not in prompt:
            return None
        return prompt['system_instruction']
    
    def get_user_prompt(self, prompt_name: str, **kwargs) -> Optional[str]:
        """Get the user prompt template and format it with provided kwargs."""
        prompt = self.get_prompt(prompt_name)
        if not prompt or 'user_prompt' not in prompt:
            return None
        
        try:
            return prompt['user_prompt'].format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing required parameter for prompt '{prompt_name}': {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error formatting prompt '{prompt_name}': {str(e)}")
            return None
    
    def create_or_update_prompt(self, name: str, description: str, system_instruction: str, 
                               user_prompt: str, created_by_email: str) -> bool:
        """Create or update a prompt in the database"""
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            logger.error("No tenant ID available, cannot create prompt")
            return False
            
        try:
            create_prompt(tenant_id, name, description, system_instruction, user_prompt, created_by_email)
            # Refresh cached prompts
            self._load_all_prompts()
            return True
        except Exception as e:
            logger.error(f"Error creating/updating prompt '{name}': {str(e)}")
            return False
    
    def rollback_prompt_version(self, name: str, target_version: int, updated_by_email: str) -> bool:
        """Rollback a prompt to a specific version"""
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            logger.error("No tenant ID available, cannot rollback prompt")
            return False
            
        try:
            success = rollback_prompt(tenant_id, name, target_version, updated_by_email)
            if success:
                # Refresh cached prompts
                self._load_all_prompts()
            return success
        except Exception as e:
            logger.error(f"Error rolling back prompt '{name}' to version {target_version}: {str(e)}")
            return False
    
    def delete_prompt(self, name: str) -> bool:
        """Delete a prompt from the database"""
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            logger.error("No tenant ID available, cannot delete prompt")
            return False
            
        try:
            success = delete_prompt(tenant_id, name)
            if success:
                # Remove from cache
                self.prompts.pop(name, None)
            return success
        except Exception as e:
            logger.error(f"Error deleting prompt '{name}': {str(e)}")
            return False

    def migrate_file_prompts(self, created_by_email: str = 'system@migration') -> bool:
        """Migrate prompts from files to database"""
        tenant_id = self._get_tenant_id()
        if not tenant_id:
            logger.error("No tenant ID available, cannot migrate prompts")
            return False
            
        if not os.path.exists(self.prompts_dir):
            logger.warning(f"Prompts directory '{self.prompts_dir}' does not exist.")
            return True
            
        migrated_count = 0
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith('.json'):
                prompt_name = os.path.splitext(filename)[0]
                try:
                    with open(os.path.join(self.prompts_dir, filename), 'r') as f:
                        prompt_data = json.load(f)
                        
                    # Check if prompt already exists in database
                    existing = get_prompt_by_name(tenant_id, prompt_name)
                    if not existing:
                        migrate_prompt_from_file(tenant_id, prompt_data, created_by_email)
                        migrated_count += 1
                        logger.info(f"Migrated prompt: {prompt_name}")
                    else:
                        logger.info(f"Prompt '{prompt_name}' already exists in database, skipping")
                        
                except Exception as e:
                    logger.error(f"Error migrating prompt '{prompt_name}': {str(e)}")
                    
        logger.info(f"Migration completed. Migrated {migrated_count} prompts")
        # Refresh cached prompts
        self._load_all_prompts()
        return True

# Create a singleton instance
prompt_manager = PromptManager()

def get_prompt_manager() -> PromptManager:
    """Get the singleton PromptManager instance."""
    return prompt_manager
