import os
import glob
import time
import logging
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from blueprints.auth import require_auth, is_admin_user

admin_bp = Blueprint('admin', __name__)

# Session directory and constants
SESSION_DIR = 'flask_session'
MAX_SESSION_FILES = 20

def perform_session_cleanup(force_all=False):
    """Perform the actual session cleanup logic.
    
    Args:
        force_all: If True, ignores age check and cleans all but the most recent files
    """
    try:
        # Get all session files
        session_files = glob.glob(f"{SESSION_DIR}/*")
        
        # Skip if we don't have too many files and not forcing cleanup
        if len(session_files) <= MAX_SESSION_FILES and not force_all:
            logging.info(f"No session cleanup needed. {len(session_files)} files found.")
            return 0
            
        # Sort files by modification time (oldest first)
        session_files.sort(key=os.path.getmtime)
        
        # Delete the oldest files, keeping MAX_SESSION_FILES
        files_to_delete = session_files[:-MAX_SESSION_FILES] if len(session_files) > MAX_SESSION_FILES else []
        
        # If forcing, delete more files but always keep at least 5 most recent
        if force_all and len(session_files) > 5:
            files_to_delete = session_files[:-5]  # Keep only 5 most recent files
            
        deleted_count = 0
        
        for file_path in files_to_delete:
            try:
                # Only delete files older than 24 hours to avoid active sessions
                # Unless force_all is True
                file_age = time.time() - os.path.getmtime(file_path)
                if force_all or file_age > 86400:  # 24 hours in seconds
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
                # Perform standard cleanup (respects age)
                deleted_count = perform_session_cleanup(force_all=False)
                if deleted_count > 0:
                    flash(f'Successfully cleaned up {deleted_count} old session files.', 'success')
                else:
                    flash('No session files needed cleaning at this time.', 'info')
            except Exception as e:
                logging.error(f"Session cleanup error: {str(e)}")
                flash(f'Error cleaning up sessions: {str(e)}', 'error')
                
        elif action == 'force_cleanup':
            try:
                # Force more aggressive cleanup
                deleted_count = perform_session_cleanup(force_all=True)
                if deleted_count > 0:
                    flash(f'Successfully cleaned up {deleted_count} session files (forced mode).', 'success')
                else:
                    flash('No session files were cleaned up.', 'info')
            except Exception as e:
                logging.error(f"Forced session cleanup error: {str(e)}")
                flash(f'Error performing forced cleanup: {str(e)}', 'error')
                
    # Get session file stats
    stats = {
        'total_files': 0,
        'size_bytes': 0,
        'oldest_file': None,
        'newest_file': None
    }
    
    try:
        session_files = glob.glob(f"{SESSION_DIR}/*")
        stats['total_files'] = len(session_files)
        
        if session_files:
            # Calculate total size
            stats['size_bytes'] = sum(os.path.getsize(f) for f in session_files)
            
            # Get oldest and newest files
            files_with_times = [(f, os.path.getmtime(f)) for f in session_files]
            oldest = min(files_with_times, key=lambda x: x[1])
            newest = max(files_with_times, key=lambda x: x[1])
            
            stats['oldest_file'] = {
                'path': oldest[0],
                'time': datetime.fromtimestamp(oldest[1]).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            stats['newest_file'] = {
                'path': newest[0],
                'time': datetime.fromtimestamp(newest[1]).strftime('%Y-%m-%d %H:%M:%S')
            }
    except Exception as e:
        logging.error(f"Error getting session stats: {str(e)}")
        flash(f'Error retrieving session information: {str(e)}', 'error')
    
    return render_template('manage_sessions.html', 
                          stats=stats,
                          MAX_SESSION_FILES=MAX_SESSION_FILES,
                          authenticated=True)

# Utility route for testing session cleanup without admin authentication
@admin_bp.route('/util/cleanup-sessions/<action>')
def util_cleanup_sessions(action):
    """Utility route for testing session cleanup.
    
    This is a temporary development route that should be disabled in production.
    """
    try:
        if action == 'status':
            # Get session file stats
            session_files = glob.glob(f"{SESSION_DIR}/*")
            count = len(session_files)
            size_bytes = sum(os.path.getsize(f) for f in session_files) if session_files else 0
            size_kb = size_bytes / 1024
            
            return f"Session files: {count}, Total size: {size_kb:.2f} KB"
            
        elif action == 'cleanup':
            # Standard cleanup
            deleted = perform_session_cleanup(force_all=False)
            return f"Cleaned up {deleted} session files"
            
        elif action == 'force-cleanup':
            # Aggressive cleanup
            deleted = perform_session_cleanup(force_all=True)
            return f"Force-cleaned {deleted} session files"
            
        else:
            return "Invalid action. Use 'status', 'cleanup', or 'force-cleanup'"
            
    except Exception as e:
        return f"Error: {str(e)}"