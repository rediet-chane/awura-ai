import httpx
import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

async def check_gmail_actions():
    token = os.getenv("ZAPIER_TOKEN")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    
    # Get Gmail-specific actions
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "list_enabled_zapier_actions",
            "arguments": {
                "selected_api": "GoogleMailV2CLIAPI"   
            }
        }
    }
    
    print("🔍 Fetching Gmail actions...")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://mcp.zapier.com/api/v1/connect",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            for line in response.text.split('\n'):
                if line.startswith('data:'):
                    data_str = line[5:].strip()
                    if data_str and data_str != '[DONE]':
                        try:
                            data = json.loads(data_str)
                            if 'result' in data:
                                result = data['result']
                                if 'content' in result:
                                    for content in result['content']:
                                        if 'text' in content:
                                            text = content['text']
                                            print(text)
                                            # Parse the JSON
                                            try:
                                                parsed = json.loads(text)
                                                print("\n📧 Available Gmail Actions:")
                                                print("=" * 40)
                                                for item in parsed:
                                                    if isinstance(item, dict):
                                                        print(f"\nApp: {item.get('app', 'Unknown')}")
                                                        print(f"Selected API: {item.get('selected_api', 'Unknown')}")
                                                        print("Actions:")
                                                        for action in item.get('actions', []):
                                                            print(f"  • {action.get('name', 'Unknown')}")
                                                            print(f"    Key: {action.get('key', 'Unknown')}")
                                                            print(f"    Type: {action.get('tool', 'Unknown')}")
                                                print("\n" + "=" * 40)
                                                print("💡 Use the 'key' value for the action parameter!")
                                            except:
                                                pass
                        except Exception as e:
                            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_gmail_actions())