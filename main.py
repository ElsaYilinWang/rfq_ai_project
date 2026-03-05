"""
RFQ AI Project — First API Call
================================
This script sends a simple prompt to the Claude API and prints the response.
It is the foundation for future procurement automation modules.
"""

import os
from anthropic import Anthropic

# ---------------------------------------------------------------
# 1. Load the API key from the .env file
# ---------------------------------------------------------------
# python-dotenv reads key=value pairs from a file called .env
# and makes them available as environment variables.
# This keeps your secret API key OUT of your code.

from dotenv import load_dotenv
load_dotenv()  # reads .env in the same folder

# ---------------------------------------------------------------
# 2. Create the API client
# ---------------------------------------------------------------
# The Anthropic client automatically looks for an environment
# variable called ANTHROPIC_API_KEY. Because we loaded .env above,
# that variable is now set.

client = Anthropic()

# ---------------------------------------------------------------
# 3. Send a message to Claude
# ---------------------------------------------------------------
# This time we ask Claude to extract structured data from an RFQ
# and return it as JSON — not plain English.

message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            
            "content": """Extract the RFQ information from the text below.

RFQ text:
Siemens motor 5.5kW quantity 3 delivery 6 weeks

Return a JSON object with these fields:
- manufacturer
- product
- power_rating
- quantity (as a number)
- delivery_time

Return valid JSON only.
Do not include any explanation or extra text.
Do not wrap the JSON in markdown code fences."""

        }
    ]
)

# ---------------------------------------------------------------
# 4. Parse the JSON response into a Python dictionary
# ---------------------------------------------------------------
# json.loads() converts a JSON string into a Python dictionary.
# We wrap it in try/except because LLM output is not guaranteed
# to be valid JSON every time.

import json

raw_response = message.content[0].text

try:
    rfq_data = json.loads(raw_response)

    print("\n--- Parsed RFQ Data ---\n")
    print(f"Manufacturer:  {rfq_data['manufacturer']}")
    print(f"Product:       {rfq_data['product']}")
    print(f"Power Rating:  {rfq_data['power_rating']}")
    print(f"Quantity:      {rfq_data['quantity']}")
    print(f"Delivery Time: {rfq_data['delivery_time']}")

except json.JSONDecodeError:
    print("\n--- Error: Claude did not return valid JSON ---\n")
    print("Raw response was:")
    print(raw_response)

# ---------------------------------------------------------------
# 5. (Optional) Inspect the full response object
# ---------------------------------------------------------------
# Uncomment the lines below to see the complete API response,
# including metadata like token usage, stop reason, and model info.
#
# print("\n--- Full Response Object ---\n")
# print(message)
