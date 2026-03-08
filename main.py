"""
RFQ AI Project — Extraction Module
====================================
This module extracts structured RFQ data from raw text using Claude.
"""

import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

import logging

logging.basicConfig(
    filename="rfq_extract.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ---------------------------------------------------------------
# Setup — runs once when the script starts
# ---------------------------------------------------------------

load_dotenv()
client = Anthropic()


# ---------------------------------------------------------------
# The extraction function
# ---------------------------------------------------------------

def extract_rfq(text):
    """
    Takes raw RFQ text and returns a structured dictionary.
    """

    logging.info(f"Extracting RFQ — input length: {len(text)} characters")

    prompt = f"""You are a procurement data extraction assistant.

Extract RFQ information from the text below.

RFQ text:
{text}

Return a JSON object with exactly these fields:
- manufacturer: the brand or manufacturer name
- product: the product type followed by model number (e.g. "motor 5.5kW", "contactor LC1D25")
- quantity: the number of units as an integer
- delivery_time: the delivery or lead time as a specific timeframe (e.g. "6 weeks")

Rules:
- Return valid JSON only.
- Do not include any explanation or extra text.
- Do not wrap the JSON in markdown code fences.
- If a field is not mentioned in the text, use null.
- For product, always put the product type before the model number.
- Words like "ASAP" or "urgent" are not specific delivery times. Use null instead."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    raw_response = message.content[0].text

    try:
        rfq_data = json.loads(raw_response)
        logging.info(f"Extraction successful — fields: {list(rfq_data.keys())}")
        return rfq_data
    except json.JSONDecodeError:
        logging.error(f"JSON parsing failed — raw response: {raw_response}")
        print("Error: Claude did not return valid JSON")
        return None
    

# ---------------------------------------------------------------
# Validation
# ---------------------------------------------------------------

REQUIRED_FIELDS = ["manufacturer", "product", "quantity", "delivery_time"]

def validate_rfq(rfq_data):
    """
    Checks that all required fields exist and are not empty.
    Returns a list of problems found. Empty list means all good.
    """
    problems = []

    for field in REQUIRED_FIELDS:
        if field not in rfq_data:
            problems.append(f"Missing field: {field}")
        elif rfq_data[field] is None or rfq_data[field] == "":
            problems.append(f"Empty field: {field}")

    return problems

# ---------------------------------------------------------------
# Test the function
# ---------------------------------------------------------------

if __name__ == "__main__":
    test_text_2 = "ABB drive 22kW quantity 10 delivery 4 weeks"

    result_2 = extract_rfq(test_text_2)

    if result_2:
        print("\n--- Second RFQ ---\n")
        print(f"Manufacturer:  {result_2['manufacturer']}")
        print(f"Product:       {result_2['product']}")
        print(f"Power Rating:  {result_2['power_rating']}")
        print(f"Quantity:      {result_2['quantity']}")
        print(f"Delivery Time: {result_2['delivery_time']}")

    test_text = "Siemens motor 5.5kW quantity 3 delivery 6 weeks"

    result = extract_rfq(test_text)

    if result:
        problems = validate_rfq(result)

        if problems:
            print("\n--- Validation Issues ---\n")
            for p in problems:
                print(f"  WARNING: {p}")
        else:
            print("\n--- RFQ Valid ---\n")

        print(f"Manufacturer:  {result['manufacturer']}")
        print(f"Product:       {result['product']}")
        print(f"Quantity:      {result['quantity']}")
        print(f"Delivery Time: {result['delivery_time']}")
    
    # Third test — vague input to test validation
    test_text_3 = "need some parts soon"

    result_3 = extract_rfq(test_text_3)

    if result_3:
        problems_3 = validate_rfq(result_3)

        if problems_3:
            print("\n--- Validation Issues ---\n")
            for p in problems_3:
                print(f"  WARNING: {p}")
        else:
            print("\n--- RFQ Valid ---\n")

        print(result_3)