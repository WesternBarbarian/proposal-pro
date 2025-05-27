
import logging
import json
import psycopg2.extras
from datetime import datetime
from db.connection import get_db_connection
from db.tenants import get_tenant_id_by_user_email

logger = logging.getLogger(__name__)

def create_proposal(estimate_id: str, proposal_content: str, user_email: str, status: str = 'draft'):
    """Create a new proposal in the database"""
    try:
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {user_email}")
            return None
        
        query = """
        INSERT INTO proposals (tenant_id, estimate_id, proposal_content, status, created_by_email)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING proposal_id
        """
        
        params = (tenant_id, estimate_id, proposal_content, status, user_email)
        
        # Use direct connection for proper transaction handling
        conn = get_db_connection()
        
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                conn.commit()
                
                if result:
                    proposal_id = result['proposal_id']
                    logger.info(f"Created proposal with ID: {proposal_id}")
                    return str(proposal_id)
                
        except Exception as e:
            conn.rollback()
            logger.error(f"Error executing create proposal query: {e}")
            raise
        
        return None
        
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        return None

def update_proposal(proposal_id: str, proposal_content: str, user_email: str, status: str = None):
    """Update an existing proposal"""
    try:
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {user_email}")
            return False
        
        # Build query dynamically based on what we're updating
        if status:
            query = """
            UPDATE proposals 
            SET proposal_content = %s, status = %s, updated_at = now()
            WHERE proposal_id = %s AND tenant_id = %s AND deleted_at IS NULL
            """
            params = (proposal_content, status, proposal_id, tenant_id)
        else:
            query = """
            UPDATE proposals 
            SET proposal_content = %s, updated_at = now()
            WHERE proposal_id = %s AND tenant_id = %s AND deleted_at IS NULL
            """
            params = (proposal_content, proposal_id, tenant_id)
        
        # Use direct connection for proper transaction handling
        conn = get_db_connection()
        
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()
                logger.info(f"Updated proposal {proposal_id}")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error executing update proposal query: {e}")
            raise
        
    except Exception as e:
        logger.error(f"Error updating proposal {proposal_id}: {e}")
        return False

def get_proposal(proposal_id: str, user_email: str):
    """Get a proposal by ID"""
    try:
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {user_email}")
            return None
        
        query = """
        SELECT proposal_id, estimate_id, proposal_content, status, created_by_email, created_at, updated_at
        FROM proposals 
        WHERE proposal_id = %s AND tenant_id = %s AND deleted_at IS NULL
        """
        
        params = (proposal_id, tenant_id)
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                
                if result:
                    return dict(result)
                
        except Exception as e:
            logger.error(f"Error executing get proposal query: {e}")
            raise
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting proposal {proposal_id}: {e}")
        return None

def get_proposals_by_estimate(estimate_id: str, user_email: str):
    """Get all proposals for a specific estimate"""
    try:
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {user_email}")
            return []
        
        query = """
        SELECT proposal_id, estimate_id, proposal_content, status, created_by_email, created_at, updated_at
        FROM proposals 
        WHERE estimate_id = %s AND tenant_id = %s AND deleted_at IS NULL
        ORDER BY created_at DESC
        """
        
        params = (estimate_id, tenant_id)
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error executing get proposals by estimate query: {e}")
            raise
        
        return []
        
    except Exception as e:
        logger.error(f"Error getting proposals for estimate {estimate_id}: {e}")
        return []

def get_all_proposals(user_email: str):
    """Get all proposals for a tenant"""
    try:
        tenant_id = get_tenant_id_by_user_email(user_email)
        if not tenant_id:
            logger.error(f"No tenant found for user: {user_email}")
            return []
        
        query = """
        SELECT proposal_id, estimate_id, proposal_content, status, created_by_email, created_at, updated_at
        FROM proposals 
        WHERE tenant_id = %s AND deleted_at IS NULL
        ORDER BY created_at DESC
        """
        
        params = (tenant_id,)
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"Error executing get all proposals query: {e}")
            raise
        
        return []
        
    except Exception as e:
        logger.error(f"Error getting all proposals: {e}")
        return []
