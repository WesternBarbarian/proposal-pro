
import os
import logging
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from flask import g, current_app

# Configure logging
logger = logging.getLogger(__name__)

# Global connection pool
_pool = None

def get_db_pool():
    """
    Create or return the existing database connection pool
    """
    global _pool
    
    if _pool is None:
        # Get database URL from environment variables
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        try:
            # Create a connection pool with 1-10 connections
            _pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=database_url
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Error creating database connection pool: {e}")
            raise
    
    return _pool

def get_db_connection():
    """
    Get a database connection from the pool
    """
    if 'db_conn' not in g:
        pool = get_db_pool()
        g.db_conn = pool.getconn()
    
    return g.db_conn

def close_db_connection(e=None):
    """
    Release the database connection back to the pool
    """
    db_conn = g.pop('db_conn', None)
    
    if db_conn is not None:
        pool = get_db_pool()
        pool.putconn(db_conn)

def init_app(app):
    """
    Initialize the database connection with the Flask app
    """
    app.teardown_appcontext(close_db_connection)

def execute_query(query, params=None, fetch=True):
    """
    Execute a database query
    
    Args:
        query (str): SQL query to execute
        params (tuple or dict): Parameters for the query
        fetch (bool): Whether to fetch results (True) or not (False)
        
    Returns:
        list: Query results as a list of dictionaries if fetch is True
        None: If fetch is False (for INSERT, UPDATE, DELETE operations)
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            
            if fetch:
                results = cur.fetchall()
                return [dict(row) for row in results]
            else:
                conn.commit()
                return None
    except Exception as e:
        conn.rollback()
        logger.error(f"Database query error: {e}")
        raise
