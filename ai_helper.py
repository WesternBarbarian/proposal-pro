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

class Request(BaseModel):
    item: str = Field(description="The name of the item, if unclear or not available")
    quantity: int = Field(description="The quantity of items needed, if unclear or not available, please return zero")

class Requests(BaseModel):
    notes: str = Field(description="Any notes about the project, if any")
    details: List[Request] = Field(description="The list of items with the item name and quantity.")

def analyze_project(description: str, customer: Customer) -> dict:
    prompt = f"""
    Analyze this construction project with customer details:
    Customer: {customer.dict()}
    Project Description: {description}

    Extract the required information and return as JSON with:
    - Project scope
    - Required materials with quantities
    - Estimated timeline
    - Work items with quantities
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