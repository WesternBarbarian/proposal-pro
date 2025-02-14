import google.generativeai as genai
import os
import json
from pydantic import BaseModel, Field
from typing import List

# Configure Gemini AI
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-pro')

class Customer(BaseModel):
    name: str = Field(description="The name of the customer, if not visible, please return 'unknown'")
    phone: str = Field(description="The phone number of the customer, if not visible, please return 'unknown'")
    email: str = Field(description="The email address of the customer, if not visible, please return 'unknown'")
    address: str = Field(description="The address of the customer, if not visible, please return 'unknown'")
    project_address: str = Field(description="The address of the project, if not visible, please return 'same'")

def analyze_project(description: str) -> dict:
    prompt = f"""
    Analyze this construction project description and extract all information:
    {description}

    Extract and return a JSON object with:
    - Customer information (name, phone, email, address, project_address)
    - Project scope
    - Required materials with quantities
    - Estimated timeline
    - Work items with quantities

    Format the response as:
    {{
        "customer": {{
            "name": "...",
            "phone": "...",
            "email": "...",
            "address": "...",
            "project_address": "..."
        }},
        "scope": "...",
        "materials": [...],
        "timeline": "...",
        "items": [
            {{"type": "item_name", "quantity": number}},
            ...
        ]
    }}
    """

    response = model.generate_content(prompt)
    return json.loads(response.text)

def generate_proposal(project_details: dict, customer: Customer, total_cost: float) -> str:
    prompt = f"""
    Generate a professional construction proposal based on:
    Customer Information:
    - Name: {customer.name}
    - Phone: {customer.phone}
    - Email: {customer.email}
    - Address: {customer.address}
    - Project Address: {customer.project_address}

    Project Details: {project_details}
    Total Cost: ${total_cost:,.2f}

    Include:
    - Executive summary
    - Scope of work
    - Timeline
    - Cost breakdown
    - Terms and conditions
    """

    response = model.generate_content(prompt)
    return response.text