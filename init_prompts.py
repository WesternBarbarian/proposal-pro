
import logging
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
        
        with app.app_context():
            prompt_manager = get_prompt_manager()
            
            # Migrate prompts from files to database
            success = prompt_manager.migrate_file_prompts()
            
            if success:
                logger.info("Prompts migrated successfully!")
            else:
                logger.error("Failed to migrate prompts")
                
            return success
            
    except Exception as e:
        logger.error(f"Error during prompt initialization: {str(e)}")
        return False

if __name__ == "__main__":
    init_prompts()
