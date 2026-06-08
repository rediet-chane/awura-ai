import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_github_token():
    token = os.getenv("GITHUB_TOKEN")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Awura-AI-Test"
    }
    
    print("🔍 Testing GitHub Token Permissions...")
    print("=" * 50)
    
    # 1. Test authentication
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.github.com/user", headers=headers)
        if r.status_code == 200:
            user = r.json()
            print(f"✅ Authenticated as: {user.get('login')}")
        else:
            print(f"❌ Auth failed: {r.status_code} - {r.text}")
            return
    
    # 2. Test listing repositories
    async with httpx.AsyncClient() as client:
        r = await client.get("https://api.github.com/user/repos?per_page=5", headers=headers)
        if r.status_code == 200:
            repos = r.json()
            print(f"✅ Can list repos. Found {len(repos)} repos")
            for repo in repos[:3]:
                print(f"   - {repo['name']}")
        else:
            print(f"❌ Cannot list repos: {r.status_code}")
    
    # 3. Test creating a repository
    async with httpx.AsyncClient() as client:
        test_repo = "test-permissions-check"
        r = await client.post("https://api.github.com/user/repos",
            json={"name": test_repo, "auto_init": True, "private": False},
            headers=headers)
        
        if r.status_code == 201:
            print(f"✅ Can CREATE repositories! Created '{test_repo}'")
            # Clean up - delete the test repo
            await client.delete(f"https://api.github.com/repos/rediet-chane/{test_repo}", headers=headers)
            print(f"   Deleted test repo")
        elif r.status_code == 403:
            error = r.json()
            print(f"⚠️ Cannot CREATE repos: {error.get('message', 'Permission denied')}")
            print("   Need 'Contents' permission set to Read and write")
        else:
            print(f"❌ Create failed: {r.status_code} - {r.text}")

asyncio.run(test_github_token())