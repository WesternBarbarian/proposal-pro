import os
import glob
import time
import logging
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, session, render_template, current_app
from blueprints.auth import require_auth
from db.tenants import is_admin_user, get_tenant_id_by_user_email
from session_manager import get_tenant_session_manager

admin_bp = Blueprint('admin', __name__)

def perform_session_cleanup(force_all=False):
    """Perform the actual session cleanup logic.
    
    Args:
        force_all: If True, ignores age check and cleans all but the most recent files
    """
    try:
        # Get configuration from current_app
        session_dir = current_app.config['SESSION_FILE_DIR']
        max_files = current_app.config['MAX_SESSION_FILES']
        cleanup_threshold = current_app.config['SESSION_CLEANUP_THRESHOLD']
        
        # Get all session files
        session_files = glob.glob(f"{session_dir}/*")
        
        # Skip if we don't have too many files and not forcing cleanup
        if len(session_files) <= max_files and not force_all:
            logging.info(f"No session cleanup needed. {len(session_files)} files found.")
            return 0
            
        # Sort files by modification time (oldest first)
        session_files.sort(key=os.path.getmtime)
        
        # Delete the oldest files, keeping max_files
        files_to_delete = session_files[:-max_files] if len(session_files) > max_files else []
        
        # If forcing, delete more files but always keep at least 5 most recent
        if force_all and len(session_files) > 5:
            files_to_delete = session_files[:-5]  # Keep only 5 most recent files
            
        deleted_count = 0
        
        for file_path in files_to_delete:
            try:
                # Only delete files older than cleanup_threshold to avoid active sessions
                # Unless force_all is True
                file_age = time.time() - os.path.getmtime(file_path)
                if force_all or file_age > cleanup_threshold:
                    os.remove(file_path)
                    logging.info(f"Cleaned up session file: {file_path}")
                    deleted_count += 1
            except Exception as e:
                logging.error(f"Error removing session file {file_path}: {str(e)}")
                
        return deleted_count
    except Exception as e:
        logging.error(f"Error in session cleanup: {str(e)}")
        return 0

@admin_bp.route('/manage-sessions', methods=['GET', 'POST'])
@require_auth
def manage_sessions():
    """Admin route for manually managing session files."""
    # Only allow specific admin users
    if not is_admin_user(session.get('user_email')):
        flash('Access denied. You are not authorized to manage sessions.', 'error')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # Handle session cleanup requests
        action = request.form.get('action')
        
        if action == 'cleanup':
            try:
                session_manager = get_tenant_session_manager()
                user_email = session.get('user_email')
                
                # Check if user is super admin (can clean all tenants)
                if is_admin_user(user_email) and session.get('user_role') == 'SUPER_ADMIN':
                    # Super admin can clean all tenant sessions
                    deleted_count = session_manager.cleanup_all_tenant_sessions()
                    flash(f'Successfully cleaned up {deleted_count} old session files across all tenants.', 'success')
                else:
                    # Regular tenant admin can only clean their own tenant's sessions
                    tenant_id = session.get('tenant_id')
                    if not tenant_id:
                        tenant_id = get_tenant_id_by_user_email(user_email)
                    
                    if tenant_id:
                        deleted_count = session_manager.cleanup_tenant_sessions(tenant_id)
                        flash(f'Successfully cleaned up {deleted_count} old session files for your tenant.', 'success')
                    else:
                        flash('No tenant found for cleanup.', 'error')
            except Exception as e:
                logging.error(f"Session cleanup error: {str(e)}")
                flash(f'Error cleaning up sessions: {str(e)}', 'error')
                
        elif action == 'force_cleanup':
            try:
                session_manager = get_tenant_session_manager()
                user_email = session.get('user_email')
                
                # Check if user is super admin (can force clean all tenants)
                if is_admin_user(user_email) and session.get('user_role') == 'SUPER_ADMIN':
                    deleted_count = session_manager.cleanup_all_tenant_sessions(max_age_seconds=0)
                    flash(f'Successfully cleaned up {deleted_count} session files (forced mode) across all tenants.', 'success')
                else:
                    # Regular tenant admin can only force clean their own tenant's sessions
                    tenant_id = session.get('tenant_id')
                    if not tenant_id:
                        tenant_id = get_tenant_id_by_user_email(user_email)
                    
                    if tenant_id:
                        deleted_count = session_manager.cleanup_tenant_sessions(tenant_id, force_all=True)
                        flash(f'Successfully cleaned up {deleted_count} session files (forced mode) for your tenant.', 'success')
                    else:
                        flash('No tenant found for cleanup.', 'error')
            except Exception as e:
                logging.error(f"Forced session cleanup error: {str(e)}")
                flash(f'Error performing forced cleanup: {str(e)}', 'error')
                
    # Get session file stats based on user permissions
    stats = []
    
    try:
        session_manager = get_tenant_session_manager()
        user_email = session.get('user_email')
        
        # Check if user is super admin (can see all tenant stats)
        if is_admin_user(user_email) and session.get('user_role') == 'SUPER_ADMIN':
            # Super admin can see all tenant session stats
            stats = session_manager.get_all_tenant_session_stats()
        else:
            # Regular tenant admin can only see their own tenant's stats
            tenant_id = session.get('tenant_id')
            if not tenant_id:
                tenant_id = get_tenant_id_by_user_email(user_email)
            
            if tenant_id:
                tenant_stats = session_manager.get_tenant_session_stats(tenant_id)
                stats = [tenant_stats]
            else:
                flash('No tenant found for session information.', 'error')
                stats = []
    except Exception as e:
        logging.error(f"Error getting session stats: {str(e)}")
        flash(f'Error retrieving session information: {str(e)}', 'error')
        stats = []
    
    return render_template('manage_sessions.html', 
                          stats=stats,
                          MAX_SESSION_FILES=current_app.config['MAX_SESSION_FILES'],
                          authenticated=True)

# Admin-only utility routes for session cleanup
@admin_bp.route('/util/cleanup-sessions/<action>')
@require_auth
def util_cleanup_sessions(action):
    """Admin utility route for session cleanup.
    
    Requires admin authentication to prevent unauthorized access.
    """
    # Check if the user is an admin
    if not is_admin_user(session.get('user_email')):
        flash('Access denied. You are not authorized to manage sessions.', 'error')
        return redirect(url_for('index'))
        
    try:
        if action == 'status':
            # Get session file stats
            session_dir = current_app.config['SESSION_FILE_DIR']
            session_files = glob.glob(f"{session_dir}/*")
            count = len(session_files)
            size_bytes = sum(os.path.getsize(f) for f in session_files) if session_files else 0
            size_kb = size_bytes / 1024
            
            return f"Session files: {count}, Total size: {size_kb:.2f} KB"
            
        elif action == 'cleanup':
            # Standard cleanup (only files older than 24 hours)
            deleted = perform_session_cleanup(force_all=False)
            return f"Cleaned up {deleted} session files"
            
        elif action == 'force-cleanup':
            # Aggressive cleanup (keeps only 5 most recent files)
            deleted = perform_session_cleanup(force_all=True)
            return f"Force-cleaned {deleted} session files"
            
        else:
            return "Invalid action. Use 'status', 'cleanup', or 'force-cleanup'"
            
    except Exception as e:
        logging.error(f"Session cleanup utility error: {str(e)}")
        return f"Error: {str(e)}"