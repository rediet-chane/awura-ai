import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("ZAPIER_TOKEN")
ZAPIER_URL = "https://mcp.zapier.com/api/v1/connect"

def list_gmail_actions():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
    }
    
    # First, get the specific Gmail actions
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_zapier_read_action",
            "arguments": {
                "selected_api": "GoogleMailV2CLIAPI",
                "action": "list_actions",  # This might list all actions for Gmail
                "params": {}
            }
        }
    }
    
    print("Fetching Gmail actions...\n")
    
    try:
        response = httpx.post(ZAPIER_URL, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
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
            print(f"Status: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_gmail_actions()