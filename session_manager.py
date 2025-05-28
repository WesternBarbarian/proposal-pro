
import os
import glob
import time
import logging
from datetime import datetime
from flask import session, current_app
from db.tenants import get_tenant_id_by_user_email

logger = logging.getLogger(__name__)

class TenantSessionManager:
    """Manages sessions with tenant isolation."""
    
    def __init__(self, base_session_dir="flask_session"):
        self.base_session_dir = base_session_dir
        self.ensure_base_directory()
    
    def ensure_base_directory(self):
        """Ensure the base session directory exists."""
        os.makedirs(self.base_session_dir, exist_ok=True)
    
    def get_tenant_session_dir(self, tenant_id):
        """Get the session directory for a specific tenant."""
        if not tenant_id:
            return self.base_session_dir
        
        tenant_dir = os.path.join(self.base_session_dir, f"tenant_{tenant_id}")
        os.makedirs(tenant_dir, exist_ok=True)
        return tenant_dir
    
    def get_current_tenant_session_dir(self):
        """Get session directory for current user's tenant."""
        user_email = session.get('user_email')
        if not user_email:
            return self.base_session_dir
        
        tenant_id = session.get('tenant_id')
        if not tenant_id:
            try:
                tenant_id = get_tenant_id_by_user_email(user_email)
                if tenant_id:
                    session['tenant_id'] = tenant_id
            except Exception as e:
                logger.error(f"Error getting tenant ID for session management: {e}")
                return self.base_session_dir
        
        return self.get_tenant_session_dir(tenant_id)
    
    def cleanup_tenant_sessions(self, tenant_id, max_age_seconds=86400, force_all=False):
        """Clean up sessions for a specific tenant."""
        tenant_dir = self.get_tenant_session_dir(tenant_id)
        
        if not os.path.exists(tenant_dir):
            return 0
        
        deleted_count = 0
        current_time = time.time()
        
        try:
            session_files = glob.glob(f"{tenant_dir}/*")
            
            for file_path in session_files:
                try:
                    if force_all:
                        os.remove(file_path)
                        deleted_count += 1
                    else:
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            deleted_count += 1
                except OSError as e:
                    logger.warning(f"Could not remove session file {file_path}: {e}")
            
            # Remove empty tenant directory if no sessions remain
            if not os.listdir(tenant_dir):
                os.rmdir(tenant_dir)
                
        except Exception as e:
            logger.error(f"Error cleaning up tenant {tenant_id} sessions: {e}")
            raise
        
        return deleted_count
    
    def cleanup_all_tenant_sessions(self, max_age_seconds=86400):
        """Clean up sessions for all tenants."""
        total_deleted = 0
        
        # Get all tenant directories
        tenant_dirs = glob.glob(f"{self.base_session_dir}/tenant_*")
        
        for tenant_dir in tenant_dirs:
            tenant_id = os.path.basename(tenant_dir).replace("tenant_", "")
            try:
                deleted = self.cleanup_tenant_sessions(tenant_id, max_age_seconds)
                total_deleted += deleted
            except Exception as e:
                logger.error(f"Failed to cleanup sessions for tenant {tenant_id}: {e}")
        
        # Also cleanup any sessions in the base directory (legacy or orphaned)
        try:
            current_time = time.time()
            base_session_files = glob.glob(f"{self.base_session_dir}/*")
            base_session_files = [f for f in base_session_files if os.path.isfile(f)]
            
            for file_path in base_session_files:
                try:
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > max_age_seconds:
                        os.remove(file_path)
                        total_deleted += 1
                except OSError:
                    pass
        except Exception as e:
            logger.error(f"Error cleaning base session directory: {e}")
        
        return total_deleted
    
    def get_tenant_session_stats(self, tenant_id):
        """Get session statistics for a specific tenant."""
        tenant_dir = self.get_tenant_session_dir(tenant_id)
        
        stats = {
            'total_files': 0,
            'size_bytes': 0,
            'oldest_file': None,
            'newest_file': None,
            'tenant_id': tenant_id
        }
        
        if not os.path.exists(tenant_dir):
            return stats
        
        try:
            session_files = glob.glob(f"{tenant_dir}/*")
            session_files = [f for f in session_files if os.path.isfile(f)]
            
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
            logger.error(f"Error getting session stats for tenant {tenant_id}: {e}")
        
        return stats
    
    def get_all_tenant_session_stats(self):
        """Get session statistics for all tenants."""
        all_stats = []
        
        # Get stats for each tenant directory
        tenant_dirs = glob.glob(f"{self.base_session_dir}/tenant_*")
        
        for tenant_dir in tenant_dirs:
            tenant_id = os.path.basename(tenant_dir).replace("tenant_", "")
            stats = self.get_tenant_session_stats(tenant_id)
            all_stats.append(stats)
        
        # Also get stats for base directory (orphaned sessions)
        base_stats = {
            'total_files': 0,
            'size_bytes': 0,
            'oldest_file': None,
            'newest_file': None,
            'tenant_id': 'orphaned'
        }
        
        try:
            base_session_files = glob.glob(f"{self.base_session_dir}/*")
            base_session_files = [f for f in base_session_files if os.path.isfile(f)]
            
            base_stats['total_files'] = len(base_session_files)
            
            if base_session_files:
                base_stats['size_bytes'] = sum(os.path.getsize(f) for f in base_session_files)
                
                files_with_times = [(f, os.path.getmtime(f)) for f in base_session_files]
                oldest = min(files_with_times, key=lambda x: x[1])
                newest = max(files_with_times, key=lambda x: x[1])
                
                base_stats['oldest_file'] = {
                    'path': oldest[0],
                    'time': datetime.fromtimestamp(oldest[1]).strftime('%Y-%m-%d %H:%M:%S')
                }
                
                base_stats['newest_file'] = {
                    'path': newest[0],
                    'time': datetime.fromtimestamp(newest[1]).strftime('%Y-%m-%d %H:%M:%S')
                }
        except Exception:
            pass
        
        if base_stats['total_files'] > 0:
            all_stats.append(base_stats)
        
        return all_stats

# Create singleton instance
tenant_session_manager = TenantSessionManager()

def get_tenant_session_manager():
    """Get the singleton TenantSessionManager instance."""
    return tenant_session_manager
