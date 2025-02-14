import google.generativeai as genai
import os
import json
from pydantic import BaseModel, Field, computed_field
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

class Item(BaseModel):
    item: str = Field(description="The name of the item, if unclear are not available, please return 'unknown'")
    unit: str = Field(description="The unit of the item, if unclear are not available, please return 'unknown'")
    price: float = Field(description="The price of the item, if unclear or not available, please return zero")

class Items(BaseModel):
    prices: List[Item] = Field(description="The list of items with the item name, unit and price.")

class Line_Item(BaseModel):
    name: str = Field(description="The name of the item, if unclear or not available, please return 'unknown'")
    unit: str = Field(description="The unit of the item, if unclear or not available, please return 'unknown'")
    price: float = Field(description="The price of the item, if unclear or not available, please return zero")
    quantity: float = Field(description="The quantity of the item, if unclear or not available, please return zero")

    @computed_field
    def total(self) -> float:
        return self.price * self.quantity

class Line_Items(BaseModel):
    lines: List[Line_Item] = Field(description="The list of line items with the item name, price, and quantity.")

    @computed_field
    def sub_total(self) -> float:
        return sum(line.total for line in self.lines)

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

def lookup_prices(project_details: dict, price_list: dict) -> Line_Items:
    lines = []
    for item in project_details['items']:
        item_name = item['type']
        quantity = item['quantity']
        price = price_list.get(item_name, 0)

        line_item = Line_Item(
            name=item_name,
            unit="unit",  # We'll need to update this when we add unit tracking
            price=price,
            quantity=quantity
        )
        lines.append(line_item)

    return Line_Items(lines=lines)

def generate_price_list(description: str) -> Items:
    prompt = f"""
    Extract pricing information from the following description and format as a structured list:
    {description}

    For each item, provide:
    - Item name
    - Unit of measurement
    - Price per unit

    Format as JSON with the structure:
    {{
        "prices": [
            {{
                "item": "item name",
                "unit": "unit of measurement",
                "price": price_value
            }},
            ...
        ]
    }}
    """

    response = model.generate_content(prompt)
    return Items.parse_raw(response.text)

def generate_proposal(project_details: dict, customer: Customer, line_items: Line_Items) -> str:
    prompt = f"""
    You are an estimator writing a new proposal for a client. Please proceed 
    step-by-step:

    1. Please write the project briefing based on these notes: 
    Project Details: {project_details}
    Customer Information:
    - Name: {customer.name}
    - Phone: {customer.phone}
    - Email: {customer.email}
    - Address: {customer.address}
    - Project Address: {customer.project_address}

    Line Items:
    {[{"item": item.name, "quantity": item.quantity, "price": item.price, "total": item.total} for item in line_items.lines]}

    2. Based on the above write a one-paragraph estimate that 
    explains the cost estimate for this project (${line_items.sub_total:.2f}), as well as the 
    anticipated timeline. Base it on the project briefing you
    just wrote, the project details and the Line Items.

    Format the response in Markdown with clear sections, including:
    - Project Overview
    - Scope of Work
    - Cost Breakdown
    - Timeline
    - Terms and Conditions
    """

    response = model.generate_content(prompt)
    return response.text