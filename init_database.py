
from app import app
from db.init_db import create_tables

if __name__ == "__main__":
    with app.app_context():
        success = create_tables()
        if success:
            print("Database tables created successfully")
        else:
            print("Failed to create database tables")
