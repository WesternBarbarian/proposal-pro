
import os
import json
import logging
from typing import Dict, Any, Optional

# Configure module logger
logger = logging.getLogger(__name__)

class PromptManager:
    """Manages loading and retrieving prompts from files."""
    
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = prompts_dir
        self.prompts: Dict[str, Any] = {}
        self._load_all_prompts()
    
    def _load_all_prompts(self) -> None:
        """Load all prompt files from the prompts directory."""
        if not os.path.exists(self.prompts_dir):
            logger.warning(f"Prompts directory '{self.prompts_dir}' does not exist.")
            return
        
        for filename in os.listdir(self.prompts_dir):
            if filename.endswith('.json'):
                prompt_name = os.path.splitext(filename)[0]
                try:
                    with open(os.path.join(self.prompts_dir, filename), 'r') as f:
                        self.prompts[prompt_name] = json.load(f)
                        logger.debug(f"Loaded prompt: {prompt_name}")
                except Exception as e:
                    logger.error(f"Error loading prompt '{prompt_name}': {str(e)}")
    
    def get_prompt(self, prompt_name: str) -> Optional[Any]:
        """Get a prompt by name."""
        if prompt_name not in self.prompts:
            logger.warning(f"Prompt '{prompt_name}' not found.")
            return None
        return self.prompts[prompt_name]
    
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

# Create a singleton instance
prompt_manager = PromptManager()

def get_prompt_manager() -> PromptManager:
    """Get the singleton PromptManager instance."""
    return prompt_manager
