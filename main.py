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
Rules:
- Return valid JSON only.
- Do not include any explanation or extra text.
- Do not wrap the JSON in markdown code fences.
- If a field is not mentioned in the text, use null.
- For product, always put the product type before the model number.
- If only a part number is given with no product description, use "part" as the product type followed by the part number exactly as written.
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
# Schema and Validation
# ---------------------------------------------------------------

RFQ_SCHEMA = {
    "manufacturer": {"type": str, "required": True},
    "product":      {"type": str, "required": True},
    "quantity":     {"type": int, "required": True},
    "delivery_time": {"type": str, "required": False},
}

def validate_rfq(rfq_data):
    """
    Validates extracted RFQ data against the schema.
    Checks: required fields present, correct data types.
    Returns a list of problems. Empty list means valid.
    """
    problems = []

    for field, rules in RFQ_SCHEMA.items():

        # Check if field exists
        if field not in rfq_data:
            if rules["required"]:
                problems.append(f"Missing required field: {field}")
            continue

        value = rfq_data[field]

        # None is acceptable for optional fields
        if value is None:
            if rules["required"]:
                problems.append(f"Required field is null: {field}")
            continue

        # Check data type
        if not isinstance(value, rules["type"]):
            problems.append(
                f"Wrong type for {field}: expected {rules['type'].__name__}, "
                f"got {type(value).__name__} ({value})"
            )

    return problems
# ---------------------------------------------------------------
# Test the function
# ---------------------------------------------------------------

if __name__ == "__main__":

    test_cases = [
        "Siemens motor 5.5kW quantity 3 delivery 6 weeks",
        "ABB drive 22kW quantity 10 delivery 4 weeks",
        "Need pricing for 10x Schneider contactor LC1D25",
        "need some parts soon",
    ]

    for i, text in enumerate(test_cases):
        print(f"\n{'=' * 50}")
        print(f"Test {i + 1}: {text}")
        print('=' * 50)

        result = extract_rfq(text)

        if result is None:
            print("EXTRACTION FAILED: No JSON returned")
            continue

        problems = validate_rfq(result)

        if problems:
            print("VALIDATION ISSUES:")
            for p in problems:
                print(f"  WARNING: {p}")
        else:
            print("VALID")

        print(f"Result: {result}")