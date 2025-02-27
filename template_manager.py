
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
        templates, _ = load_templates()
        if 0 <= template_id < len(templates):
            templates.pop(template_id)
            save_templates(templates)
            return True, "Template deleted successfully"
        return False, "Template not found"
    except Exception as e:
        return False, str(e)
