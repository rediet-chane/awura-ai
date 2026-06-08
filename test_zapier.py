import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("ZAPIER_TOKEN")
ZAPIER_URL = "https://mcp.zapier.com/api/v1/connect"

def test_zapier():
    print(f"Testing Zapier connection...")
    print(f"Token: {TOKEN[:20]}...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
    }
    
    # Test listing available actions
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "list_enabled_zapier_actions",
            "arguments": {}
        }
    }
    
    try:
        response = httpx.post(ZAPIER_URL, json=payload, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            # Check if it's SSE stream
            if 'text/event-stream' in response.headers.get('content-type', ''):
                print("\nSSE Stream Response:")
                for line in response.text.split('\n'):
                    if line.startswith('data:'):
                        print(line)
            else:
                data = response.json()
                print(f"\nResponse: {json.dumps(data, indent=2)}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_zapier()