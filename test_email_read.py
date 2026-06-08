# test_email_read.py
import httpx
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def test_email_read():
    token = os.getenv("ZAPIER_TOKEN")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    
    # Try the correct format for reading emails
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_zapier_read_action",
            "arguments": {
                "selected_api": "GoogleMailV2CLIAPI",
                "action": "message",
                "instructions": "Find recent emails",
                "output": "Return email list",
                "params": {
                    "maxResults": 5
                }
            }
        }
    }
    
    print("🔍 Testing email read...")
    print("=" * 50)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://mcp.zapier.com/api/v1/connect",
            json=payload,
            headers=headers
        )
        
        print(f"Status: {response.status_code}")
        print("\nResponse:")
        print("=" * 50)
        
        if "text/event-stream" in response.headers.get("content-type", ""):
            for line in response.text.split('\n'):
                if line.startswith('data:'):
                    data_str = line[5:].strip()
                    if data_str and data_str != '[DONE]':
                        try:
                            data = json.loads(data_str)
                            print(json.dumps(data, indent=2))
                        except:
                            print(data_str)
        else:
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_email_read())