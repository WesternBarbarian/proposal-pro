
import json
import os

def load_templates():
    try:
        with open('custom_templates.json', 'r') as f:
            return json.load(f)['templates']
    except (FileNotFoundError, json.JSONDecodeError):
        with open('default_template.json', 'r') as f:
            return json.load(f)['templates']

def save_templates(templates):
    with open('custom_templates.json', 'w') as f:
        json.dump({'templates': templates}, f, indent=4)

def add_template(template_text):
    try:
        templates = load_templates()
        if len(templates) >= 5:
            return False, "Maximum 5 templates allowed"
        templates.append(template_text)
        save_templates(templates)
        return True, "Template added successfully"
    except Exception as e:
        return False, str(e)

def delete_template(template_id):
    try:
        templates = load_templates()
        if 0 <= template_id < len(templates):
            templates.pop(template_id)
            save_templates(templates)
            return True, "Template deleted successfully"
        return False, "Template not found"
    except Exception as e:
        return False, str(e)
