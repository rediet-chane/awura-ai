# check_actions.py
import httpx
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def check_zapier_actions():
    token = os.getenv("ZAPIER_TOKEN")
    
    if not token:
        print("❌ ZAPIER_TOKEN not found in .env file")
        return
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",  # Add this!
    }
    
    # Try to list all actions
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "list_enabled_zapier_actions",
            "arguments": {}
        }
    }
    
    print("🔍 Fetching available Zapier actions...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://mcp.zapier.com/api/v1/connect",
            json=payload,
            headers=headers
        )
        
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print("\nResponse:")
        print("=" * 60)
        
        # Parse the response
        if response.status_code == 200:
            if "text/event-stream" in response.headers.get("content-type", ""):
                # Handle SSE response
                for line in response.text.split('\n'):
                    if line.startswith('data:'):
                        data_str = line[5:].strip()
                        if data_str and data_str != '[DONE]':
                            try:
                                data = json.loads(data_str)
                                if 'result' in data:
                                    result = data['result']
                                    print(json.dumps(result, indent=2))
                            except Exception as e:
                                print(f"Error parsing: {e}")
                                print(data_str)
            else:
                # Handle JSON response
                data = response.json()
                print(json.dumps(data, indent=2))
        else:
            print(f"Error: {response.text}")
    
    print("\n" + "=" * 60)
    print("💡 Based on your earlier successful email send, the action 'message' works.")
    print("For reading emails, try these commands in chat:")
    print("  - 'find email from me'")
    print("  - 'search email'")
    print("  - 'show my inbox'")
    print("\nOr check your Zapier dashboard at: https://zapier.com/app/connections")

if __name__ == "__main__":
    asyncio.run(check_zapier_actions())