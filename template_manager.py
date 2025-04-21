
import json
import os

def load_templates():
    # Try to load custom templates first
    try:
        with open('custom_templates.json', 'r') as f:
            templates = json.load(f)['templates']
            if isinstance(templates, list) and len(templates) > 0:
                # Process templates to ensure proper newlines
                return [t.replace('\\r\\n', '\n').replace('\\n', '\n') for t in templates], True
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
        
    # If custom templates fail or are empty, load default template
    try:
        with open('default_template.json', 'r') as f:
            templates = json.load(f)['templates']
            if isinstance(templates, list):
                # Process templates to ensure proper newlines
                return [t.replace('\\r\\n', '\n').replace('\\n', '\n') for t in templates], False
            return [str(templates).replace('\\r\\n', '\n').replace('\\n', '\n')], False
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return ["Default template not found. Please add a template."], False

def save_templates(templates):
    with open('custom_templates.json', 'w') as f:
        json.dump({'templates': templates}, f, indent=4)

def add_template(template_text):
    try:
        templates, _ = load_templates()
        if len(templates) >= 5:
            return False, "Maximum 5 templates allowed"
        templates.append(template_text)
        save_templates(templates)
        return True, "Template added successfully"
    except Exception as e:
        return False, str(e)

def delete_template(template_id):
    try:
        templates, using_custom = load_templates()
        
        # Only allow deleting custom templates
        if not using_custom:
            return False, "Cannot delete default templates. Add a custom template first."
            
        template_id = int(template_id)  # Ensure it's an integer
        if 0 <= template_id < len(templates):
            templates.pop(template_id)
            
            # If all templates are deleted, remove the custom_templates.json file
            if len(templates) == 0:
                try:
                    import os
                    os.remove('custom_templates.json')
                    return True, "Template deleted and falling back to default templates"
                except Exception as e:
                    return False, f"Error removing custom templates file: {str(e)}"
            else:
                save_templates(templates)
                return True, "Template deleted successfully"
        return False, "Template not found"
    except Exception as e:
        return False, str(e)
