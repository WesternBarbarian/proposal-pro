import google.generativeai as genai
import os
import json

# Configure Gemini AI
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

def analyze_project(description):
    prompt = f"""
    Analyze the following construction project description and extract key details:
    {description}
    
    Return a JSON object with:
    - Project scope
    - Required materials
    - Estimated timeline
    - List of work items with quantities
    """
    
    response = model.generate_content(prompt)
    return json.loads(response.text)

def generate_proposal(project_details, total_cost):
    prompt = f"""
    Generate a professional construction proposal based on:
    Project Details: {project_details}
    Total Cost: ${total_cost}
    
    Include:
    - Executive summary
    - Scope of work
    - Timeline
    - Cost breakdown
    - Terms and conditions
    """
    
    response = model.generate_content(prompt)
    return response.text
