from google import genai
from google.genai import types
import os
import json
import logging
from pydantic import BaseModel, Field, computed_field
from typing import List
from template_manager import load_templates

# Configure module logger
logger = logging.getLogger(__name__)

# Configure Gemini AI
api_key= os.environ['GEMINI_API_KEY']
client = genai.Client(api_key=api_key)
model = "gemini-2.0-flash"

##Project from description
class Request(BaseModel):
  item: str = Field(description="The name of the item, if unclear or not available")
  quantity: int = Field(description="The quantity of items needed, if unclear or not available, please return zero")

class Requests(BaseModel):
  notes: str = Field(description="Notes about the project, if any")
  details: list[Request] = Field(description="The list of items with the item name and quantity.")

class Item(BaseModel):
  item: str = Field(description="The name of the item, if unclear are not available, please return 'unknown'")
  unit: str = Field(description="The unit of the item, if unclear are not available, please return 'unknown'")
  price: float = Field(description="The price of the item, if unclear or not available, please return 0.0")


class Items(BaseModel):
  prices: list[Item] = Field(description="The list of items with the item name, unit and price.")

class ProjectData(BaseModel):
    # Customer information
    customer_name: str = Field(description="The name of the customer, if not visible, please return 'unknown'")
    customer_phone: str = Field(description="The phone number of the customer, if not visible, please return 'unknown'")
    customer_email: str = Field(description="The email address of the customer, if not visible, please return 'unknown'")
    customer_address: str = Field(description="The address of the customer, if not visible, please return 'unknown'")
    project_address: str = Field(description="The address of the project, if not visible, please return 'same'")
    # Project information
    notes: str = Field(description="Notes about the project, if any")
    details: list[Request] = Field(description="The list of items with the item name and quantity.")

def extract_project_data(description: str) -> tuple[dict, dict]:
    prompt = f"Extract the structured data from {description}"

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={'response_mime_type': 'application/json', 'response_schema': ProjectData})

        project_data: ProjectData = response.parsed
    except Exception as e:
        logger.error(f"Error extracting project data: {str(e)}")
        raise

    # Convert to separate customer and project dictionaries for backward compatibility
    customer = {
        "name": project_data.customer_name,
        "phone": project_data.customer_phone,
        "email": project_data.customer_email,
        "address": project_data.customer_address,
        "project_address": project_data.project_address
    }

    project = {
        "notes": project_data.notes,
        "details": [{"item": detail.item, "quantity": detail.quantity} for detail in project_data.details]
    }

    return customer, project

def extract_project_data_from_image(file_path: str) -> tuple[dict, dict]:
    import logging
    logger = logging.getLogger(__name__)
    
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        raise FileNotFoundError(f"File not found: {file_path}")
        
    logger.info(f"Uploading file from {file_path} to Gemini API")
    img_file = client.files.upload(file=file_path, config={'display_name': 'project_details'})
    logger.info(f"File uploaded successfully")

    prompt = "Extract the structured data from the following file. Include customer name, contact details, and project information."
    logger.info(f"Sending prompt to Gemini API: {prompt}")
    response = client.models.generate_content(
        model=model,
        contents=[prompt, img_file],
        config={'response_mime_type': 'application/json', 'response_schema': ProjectData}
    )
    logger.info(f"Received response from Gemini API")
    
    try:
        project_data: ProjectData = response.parsed
        logger.info(f"Response parsed successfully")
        
        if not project_data:
            logger.error("Parsed response is empty")
            raise ValueError("Failed to extract data from image")
            
        # Verify we have at least some basic data
        if not project_data.customer_name or project_data.customer_name == "unknown":
            logger.warning("Customer name not found in image")
            
        if not project_data.details or len(project_data.details) == 0:
            logger.warning("No project details found in image")
            
        logger.debug(f"Extracted project data: {project_data}")
    except Exception as e:
        logger.error(f"Error parsing response: {str(e)}")
        raise

    # Convert to separate customer and project dictionaries for backward compatibility
    customer = {
        "name": project_data.customer_name,
        "phone": project_data.customer_phone,
        "email": project_data.customer_email,
        "address": project_data.customer_address,
        "project_address": project_data.project_address
    }
    logger.info(f"Customer data: {customer}")

    project = {
        "notes": project_data.notes,
        "details": [{"item": detail.item, "quantity": detail.quantity} for detail in project_data.details]
    }
    logger.info(f"Project data: {project}")

    return customer, project


def generate_price_list_from_image(file_path: str) -> Items:
    img_file = client.files.upload(file=file_path, config={'display_name': 'price_list'})

    prompt = "Extract structured price list data from the following file"
    response = client.models.generate_content(
        model=model,
        contents=[prompt, img_file],
        config={'response_mime_type': 'application/json', 'response_schema': Items}
    )

    price_list: Items = response.parsed
    return price_list

def generate_price_list(description: str) -> Items:
  prompt = f"Extract the structured data from the following: {description}"

  response = client.models.generate_content(
      model=model,
      contents=prompt,
      config={'response_mime_type': 'application/json', 'response_schema': Items})

  price_list: Items = response.parsed


  return price_list


def analyze_project(description: str) -> dict:
  prompt = f"Extract the structured data from {description}"

  response = client.models.generate_content(
      model=model,
      contents=prompt,
      config={'response_mime_type': 'application/json', 'response_schema': Requests})

  user_request: Requests = response.parsed

  return user_request

def analyze_project_image(file_path: str) -> dict:
  img_file = client.files.upload(file=file_path, config={'display_name': 'project_details'})

  prompt = "Extract the structured data from the following file"
  response = client.models.generate_content(
      model=model,
      contents=[prompt, img_file],
      config={'response_mime_type': 'application/json', 'response_schema': Requests}
  )
  user_request: Requests = response.parsed
  return user_request

#Retrieve prices and calculate totals
class Line_Item(BaseModel):
  name: str = Field(description="The name of the item, if unclear or not available, please return 'unknown'")
  unit: str = Field(description="The unit of the item, if unclear or not available, please return 'unknown'")
  price: float = Field(description="The price of the item, if unclear or not available, please return 0.0")
  quantity: int = Field(description="The quantity of the item, if unclear or not available, please return zero")

  @computed_field
  def total(self) -> float:
    return self.price * self.quantity

class Line_Items(BaseModel):
  lines: list[Line_Item] = Field(description="The list of line items with the item name, price, and quantity.")

  @computed_field
  def sub_total(self) -> float:
      """Calculates the sum of all line item totals."""
      return sum(line.total for line in self.lines)


def lookup_prices(project_details: dict, price_list: dict) -> Line_Items:
    import logging
    logger = logging.getLogger(__name__)
    
    # First, try to use direct mapping for items if they exist in the price list
    # This will handle the case when API returns are not being processed correctly
    try:
        logger.debug("Attempting direct price lookup before using AI")
        manual_line_items = []
        
        # Create a lowercase version of the price list for case-insensitive matching
        lowercase_price_map = {}
        if isinstance(price_list, dict):
            for item_name, item_data in price_list.items():
                lowercase_price_map[item_name.lower()] = {
                    "name": item_name,  # Keep original capitalization for display
                    "unit": item_data.get("unit", "unknown"),
                    "price": float(item_data.get("price", 0.0))
                }
        
        # Try to match items from project details to price list
        if project_details and "details" in project_details:
            for detail in project_details["details"]:
                item_name = detail.get("item", "")
                quantity = detail.get("quantity", 0)
                
                # Look for an exact match or a case-insensitive match
                item_data = None
                if item_name in price_list:
                    # Direct match
                    item_data = {
                        "name": item_name,
                        "unit": price_list[item_name].get("unit", "unknown"),
                        "price": float(price_list[item_name].get("price", 0.0))
                    }
                elif item_name.lower() in lowercase_price_map:
                    # Case-insensitive match
                    item_data = lowercase_price_map[item_name.lower()]
                
                if item_data:
                    # We found a match, create a Line_Item
                    line_item = Line_Item(
                        name=item_data["name"],
                        unit=item_data["unit"],
                        price=item_data["price"],
                        quantity=quantity
                    )
                    manual_line_items.append(line_item)
                    logger.debug(f"Direct match found for {item_name}, price: {item_data['price']}")
        
        # If we have matches for all items, return the Line_Items
        if manual_line_items:
            if len(manual_line_items) == len(project_details["details"]):
                logger.debug(f"Using direct matching for all {len(manual_line_items)} items")
                return Line_Items(lines=manual_line_items)
            else:
                logger.debug(f"Direct matching found {len(manual_line_items)} items, but needed {len(project_details['details'])}")
    except Exception as e:
        logger.error(f"Error in direct price lookup: {str(e)}")
        # Continue to AI lookup if direct lookup fails
    
    # If direct lookup didn't work or didn't find all items, fall back to AI
    logger.debug("Falling back to AI for price lookup")
    sys_instruct="""##Role: You are a pricing specialist.
    You look up the price of items from the provided list.
    ##Task: Look up prices.
    ##Task Guidance: Items may have alternative names. When you know what the user means, look up the price for that item.
    If you do not know what an item is, or if it is not in the list, enter the price as zero in your response.
    If you are provided with a quantity, return the quantity for the item in the json response.
    If you are not provided with a quantity put zero. DO NOT GUESS ABOUT QUANTITY.
    Carefully review the users input and make sure you know the quantity for each item.
    IMPORTANT: Match the exact spelling and capitalization of the items in the user's request.
    ### Example 1:
    {
      "role": "user",
      "parts": [
        "I need 3 drills, work lights, and 1 ladder."
      ]
    },
    {
      "role": "model",
      "parts": [
        json
        [
          {
            "item": "Cordless Drill",
            "quantity": "3",
            "price": "79.99"
          },
          {
            "item": "LED Work Light",
            "quantity": "unknown",
            "price": "39.99"
          },
          {
            "item": "Ladder (6ft)",
            "quantity": "1",
            "price": "89.99"
          }
        ]
      ]
    }

    ### Example 2:
    {
      "role": "user",
      "parts": [
        "two leaf blowers, drills, and ladders."
      ]
    },
    {
      "role": "model",
      "parts": [
        json
        [
          {
            "item": "Leaf Blower",
            "quantity": "2",
            "price": "unknown"
          },
          {
            "item": "Cordless Drill",
            "quantity": "unknown",
            "price": "79.99"
          },
          {
            "item": "Ladder (6ft)",
            "quantity": "unknown",
            "price": "89.99"
          }
        ]
      ]
    }

    ### Example 3:
    {
      "role": "user",
      "parts": [
        "1 stud finder, 3 ceiling fans, a ladder, a circular saw, and work lights."
      ]
    },
    {
      "role": "model",
      "parts": [
        json
        [
          {
            "item": "Stud Finder",
            "quantity": "1",
            "price": "34.99"
          },
          {
            "item": "Ceiling Fan",
            "quantity": "3",
            "price": "149.99"
          },
          {
            "item": "Ladder (6ft)",
            "quantity": "1",
            "price": "89.99"
          },
          {
            "item": "Circular Saw",
            "quantity": "1",
            "price": "129.99"
          },
          {
            "item": "LED Work Light",
            "quantity": "unknown",
            "price": "39.99"
          }
        ]
      ]
    }
    """

    user_request = project_details
    prompt = f"Look up the prices from the {price_list} for the items in {user_request}"
    
    logger.debug(f"Sending prompt to Gemini API: {prompt}")
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config = types.GenerateContentConfig(
            system_instruction=sys_instruct,
            response_mime_type='application/json',
            response_schema=Line_Items,
        ),
    )
    logger.debug("Received response from Gemini API")

    line_items: Line_Items = response.parsed
    
    # Ensure we're preserving the original capitalization from the project details
    if project_details and "details" in project_details:
        matched_names = {}
        for detail in project_details["details"]:
            item_name = detail.get("item", "").lower()
            matched_names[item_name] = detail.get("item", "")  # Original capitalization
        
        # Update the line items with the original capitalization
        updated_lines = []
        for line in line_items.lines:
            original_name = matched_names.get(line.name.lower(), line.name)
            updated_line = Line_Item(
                name=original_name,
                unit=line.unit,
                price=line.price,
                quantity=line.quantity
            )
            updated_lines.append(updated_line)
        
        if updated_lines:
            line_items = Line_Items(lines=updated_lines)
    
    return line_items



#Generate proposal
def generate_proposal(project_details: dict, customer: dict, line_items: Line_Items, templates: list[str]) -> str:
    # Validate input parameters
    if not project_details:
        logger.warning("Empty project details provided to generate_proposal")
        project_details = {"notes": "", "details": []}
        
    if not customer:
        logger.warning("Empty customer information provided to generate_proposal")
        customer = {"name": "Customer", "phone": "", "email": "", "address": "", "project_address": ""}
    
    # Ensure templates are all strings and join them with clear separators
    if not templates or len(templates) == 0:
        # Fallback to load templates if none provided
        logger.info("No templates provided, loading default templates")
        templates, _ = load_templates()
    
    # Debug log to check what templates we're receiving
    logger.debug(f"Templates loaded: {templates}")
    
    # Process templates to ensure proper newlines and formatting
    processed_templates = []
    for t in templates:
        # Convert to string and properly handle newlines
        template_str = str(t).replace('\\r\\n', '\n').replace('\\n', '\n')
        processed_templates.append(template_str)
    
    # Join with clear separators
    template_examples = "\n\n=== EXAMPLE PROPOSAL ===\n\n".join(processed_templates)
    
    prompt = f"""
    You are an estimator writing a new proposal for a client. Please proceed
    step-by-step:

    1. Please write the project analysis based on these notes:
    {project_details} and this estimate: {line_items}. It is OK if
    some amounts are zero.
    2. Based on the analysis above write an estimate to {customer['name']}. Do not make up any details. Use only the information from the source files and analysis above. Prepare the proposal using the following examples to determine the voice, tone, and length of the proposal (even if it seems silly):

    {template_examples}

--
    Do not use markdown. Simply use plain text.
    """


    # Debug log template examples to verify format
    logger.debug(f"Template examples being sent to AI: {template_examples}")
    
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text