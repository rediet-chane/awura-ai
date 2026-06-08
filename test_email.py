import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("ZAPIER_TOKEN")
ZAPIER_URL = "https://mcp.zapier.com/api/v1/connect"

def send_test_email():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/event-stream",
    }
    
    # Correct format with instructions and output fields
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_zapier_write_action",
            "arguments": {
                "selected_api": "GoogleMailV2CLIAPI",
                "action": "message",
                "instructions": "Send an email to redichane123@gmail.com with subject 'Test from Awura AI' and body saying hello",
                "output": "Confirm the email was sent successfully and provide a summary",
                "params": {
                    "to": "redichane123@gmail.com",
                    "subject": "Test from Awura AI",
                    "body": "Hello! This is a test email sent via Zapier MCP integration.\n\nBest regards,\nAwura AI Assistant"
                }
            }
        }
    }
    
    print("Sending email...")
    print("="*50 + "\n")
    
    try:
        response = httpx.post(ZAPIER_URL, json=payload, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type')}")
        print("\nResponse:")
        
        if response.status_code == 200:
            # Parse SSE response
            email_sent = False
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
                                            print(f"✓ {content['text']}")
                                            email_sent = True
                                else:
                                    print(json.dumps(result, indent=2))
                                    email_sent = True
                            elif 'error' in data:
                                print(f"❌ Error: {data['error']}")
                            else:
                                print(json.dumps(data, indent=2))
                        except json.JSONDecodeError:
                            print(f"Raw: {data_str}")
            
            if email_sent:
                print("\n✅ Email sent successfully! Check your inbox.")
            else:
                print("\n⚠️ Check the response above for details.")
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    send_test_email()