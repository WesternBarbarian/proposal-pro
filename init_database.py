from app import app
from db.init_db import create_tables

if __name__ == "__main__":
    with app.app_context():
        success = create_tables()
        if success:
            print("Database tables created successfully")
            
            # Initialize price lists and templates if tables were created successfully
            from db.price_lists import initialize_price_lists
            from db.templates import initialize_templates
            initialize_price_lists()
            initialize_templates()
        else:
            print("Failed to create database tables")