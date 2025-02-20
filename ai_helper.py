from google import genai
from google.genai import types
import os
import json
from pydantic import BaseModel, Field, computed_field
from typing import List

# Configure Gemini AI
api_key= os.environ['GEMINI_API_KEY']
client = genai.Client(api_key=api_key)
model = "gemini-2.0-flash"


##Extract Customer Information

class Customer(BaseModel):
  name: str = Field(description="The name of the customer, if not visible, please return 'unknown'")
  phone: str = Field(description="The phone number of the customer, if not visible, please return 'unknown")
  email: str = Field(description="The email address of the customer, if not visible, please return 'unknown")
  address: str = Field(description="The address of the customer, if not visible, please return 'unknown")
  project_address: str = Field(description="The address of the project, if not visible, please return 'same")



def extract_customer(description: str) -> dict:
  prompt = f"Extract the structured data from {description}"

  response = client.models.generate_content(
    model=model,
    contents=prompt,
    config={'response_mime_type': 'application/json', 'response_schema': Customer})

  customer_info: Customer = response.parsed
  return customer_info


##Generate Price List
class Item(BaseModel):
  item: str = Field(description="The name of the item, if unclear are not available, please return 'unknown'")
  unit: str = Field(description="The unit of the item, if unclear are not available, please return 'unknown'")
  price: int = Field(description="The price of the item, if unclear or not available, please return zero")


class Items(BaseModel):
  prices: list[Item] = Field(description="The list of items with the item name, unit and price.")


def generate_price_list(description: str) -> Items:
  prompt = f"Extract the structured data from the following: {description}"

  response = client.models.generate_content(
      model=model,
      contents=prompt,
      config={'response_mime_type': 'application/json', 'response_schema': Items})

  price_list: Items = response.parsed


  return price_list


##Project from description
class Request(BaseModel):
  item: str = Field(description="The name of the item, if unclear or not available")
  quantity: int = Field(description="The quantity of items needed, if unclear or not available, please return zero")

class Requests(BaseModel):
  notes: str = Field(description="Notes about the project, if any")
  details: list[Request] = Field(description="The list of items with the item name and quantity.")


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
  price: int = Field(description="The price of the item, if unclear or not available, please return zero")
  quantity: int = Field(description="The quantity of the item, if unclear or not available, please return zero")

  @computed_field
  def total(self) -> int:
    return self.price * self.quantity

class Line_Items(BaseModel):
  lines: list[Line_Item] = Field(description="The list of line items with the item name, price, and quantity.")

  @computed_field
  def sub_total(self) -> int:
      """Calculates the sum of all line item totals."""
      return sum(line.total for line in self.lines)
   
    
def lookup_prices(project_details: dict, price_list: dict) -> Line_Items:
    sys_instruct="""##Role: You are a pricing specialist.
    You look up the price of items from the provided list.
    ##Task: Look up prices.
    ##Task Guidance: Items may have alternative names. When you know what the user means, look up the price for that item.
    If you do not know what an item is, or if it is not in the list, enter the price as zero in your response.
    If you are provided with a quantity, return the quantity for the item in the json response.
    If you are not provided with a quantity put zero. DO NOT GUESS ABOUT QUANTITY.
    Carefully review the users input and make sure you know the quantity for each item.
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
    price_list = price_list


    user_request= project_details

    prompt = f"Look up the prices from the {price_list} for the items in {user_request}"
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config = types.GenerateContentConfig(
            system_instruction=sys_instruct,
            response_mime_type='application/json',
            response_schema=Line_Items,
        ),
    )

    
    line_items: Line_Items = response.parsed
   
    return line_items



#Generate proposal
def generate_proposal(project_details: dict, customer: Customer, line_items: Line_Items) -> str:
    prompt = f""""
    You are an estimator writing a new proposal for a client. Please proceed
    step-by-step:

    1. Please write the project briefing based on these notes:
    {project_details} and this estimate: {line_items}. It is OK if
    some amounts are zero.
    2. Based on the above write a one-paragraph estimate to {customer} that
    explains the cost estimate for this project, as well as the
    anticipated timeline. Base it on the project briefing you
    just wrote, the project_notes and the Line_Items.
    """


    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text