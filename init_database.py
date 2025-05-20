from app import app
from db.init_db import create_tables

if __name__ == "__main__":
    with app.app_context():
        success = create_tables()
        if success:
            print("Database tables created successfully")
            
            # Only initialize price lists if tables were created successfully
            from db.price_lists import initialize_price_lists
            initialize_price_lists()
        else:
            print("Failed to create database tables")