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
# The messages.create() call is the core API interaction.
# - model:      which Claude model to use
# - max_tokens: maximum length of the response (in tokens ≈ words × 1.3)
# - messages:   a list of message objects (role + content)

message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": "Explain what an RFQ is in procurement."
        }
    ]
)

# ---------------------------------------------------------------
# 4. Print the response
# ---------------------------------------------------------------
# The API returns a Message object. The actual text lives inside
# message.content, which is a list of content blocks.
# For a simple text response, the first block's .text has what we need.

print("\n--- Claude's Response ---\n")
print(message.content[0].text)

# ---------------------------------------------------------------
# 5. (Optional) Inspect the full response object
# ---------------------------------------------------------------
# Uncomment the lines below to see the complete API response,
# including metadata like token usage, stop reason, and model info.
#
print("\n--- Full Response Object ---\n")
print(message)
