
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from blueprints.auth import require_auth
from db.tenants import is_admin_user, get_tenant_id_by_user_email
from db.drive_settings import set_drive_setting, get_drive_setting

drive_settings_bp = Blueprint('drive_settings', __name__)

@drive_settings_bp.route('/drive-settings', methods=['GET', 'POST'])
@require_auth
def manage_drive_settings():
    """Manage Google Drive folder settings for the tenant."""
    user_email = session.get('user_email')
    
    # Check if user is admin
    if not is_admin_user(user_email):
        flash('Access denied. Only admins can manage Drive settings.', 'error')
        return redirect(url_for('index'))
    
    tenant_id = get_tenant_id_by_user_email(user_email)
    if not tenant_id:
        flash('No tenant found.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            # Update settings
            root_folder = request.form.get('root_folder', 'Project Proposals')
            auto_organize = request.form.get('auto_organize') == 'on'
            subfolder_pattern = request.form.get('subfolder_pattern', '{client_name}')
            
            # Save settings
            set_drive_setting(tenant_id, 'folder_template', 'root_folder', root_folder, user_email)
            set_drive_setting(tenant_id, 'auto_organize', 'enabled', str(auto_organize).lower(), user_email)
            set_drive_setting(tenant_id, 'folder_template', 'subfolder_pattern', subfolder_pattern, user_email)
            
            flash('Drive settings updated successfully!', 'success')
            
        except Exception as e:
            flash(f'Error updating settings: {str(e)}', 'error')
    
    # Get current settings
    current_settings = {
        'root_folder': get_drive_setting(tenant_id, 'folder_template', 'root_folder', 'Project Proposals'),
        'auto_organize': get_drive_setting(tenant_id, 'auto_organize', 'enabled', 'false') == 'true',
        'subfolder_pattern': get_drive_setting(tenant_id, 'folder_template', 'subfolder_pattern', '{client_name}')
    }
    
    return render_template('drive_settings.html', 
                         settings=current_settings,
                         authenticated=True)
