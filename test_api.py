#!/usr/bin/env python3
"""
Simple test script to verify the API connection is working correctly.
"""

import asyncio
from utils import configure_openai_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def main():
    print("Testing API connection...")
    client = configure_openai_client()
    
    try:
        # Try a simple chat completion
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, are you working correctly?"}
            ],
            max_tokens=50
        )
        
        print("\nAPI Connection Test: SUCCESS ✅")
        print("Response content:")
        print(response.choices[0].message.content)
        return True
    except Exception as e:
        print("\nAPI Connection Test: FAILED ❌")
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        print("\nRecommendations:")
        print("- Check your API key and base URL in the .env file")
        print("- Ensure the API endpoint is accessible from your network")
        print("- Check if the endpoint requires additional authentication")