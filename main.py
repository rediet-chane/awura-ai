import datetime, re, httpx, json, ast, operator, os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Tuple, Any
import asyncio

from database import init_db, query_db, save_chat, get_all_chats, get_chat, delete_chat
from files import save_file, get_file_context, remove_file, list_files

load_dotenv()

# IMPORTANT: Your ZAPIER_TOKEN is the FULL URL from Zapier MCP
# Example: "NTNhMmU2ODUtNDliZS00OTYxLTgzZDctZWVhOGUxMDIyMGIz:xxxxx"
ZAPIER_TOKEN = os.getenv("ZAPIER_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}

def safe_eval(node):
    if isinstance(node, ast.Constant): 
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -safe_eval(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    raise ValueError("Invalid")

# ── Tool detection with priority ─────────────────────────────────────────────
TOOLS = [
    {"name": "github_create_repo", "keywords": ["create repo", "create a repo", "new repo", "create repository", "make a repo", "create reposteries"]},
    {"name": "github_list_repos", "keywords": ["list all repos", "all repositories", "list repos", "my repos", "my repositories", "show all repos", "see all my repos", "list my github repos", "show my repos"]},
    {"name": "zapier_github", "keywords": ["github", "find repo", "create issue", "create branch", "create gist", "pull request"]},
    {"name": "zapier_email_send", "keywords": ["send email", "email to", "mail to", "write email", "send message", "@gmail", "@yahoo", "@outlook"]},
    {"name": "get_current_datetime", "keywords": ["time", "date", "today", "now", "what day", "what time", "clock"]},
    {"name": "query_database", "keywords": ["employee", "project", "team", "staff", "database", "department", "show me employees", "list projects", "how many", "count", "total employees", "people in the company"]},
    {"name": "calculate", "keywords": ["calculate", "compute", "math", "sum", "multiply", "divide", "plus", "minus", "times"]},
]

def detect_tool(msg: str):
    m = msg.lower().strip()
    
    # Email detection - SEND
    if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', msg):
        if any(k in m for k in ["send", "email", "mail"]):
            return "zapier_email_send"
    
    # Check other tools in order
    for t in TOOLS:
        if any(kw in m for kw in t["keywords"]):
            return t["name"]
    
    return None

# ── GitHub API Helpers ─────────────────────────────────────────────────────
async def github_api_request(method: str, endpoint: str, data: dict = None) -> Tuple[int, Any]:
    if not GITHUB_TOKEN:
        return 401, {"error": "GITHUB_TOKEN not set"}
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Awura-AI"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://api.github.com/{endpoint}"
            
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, json=data, headers=headers)
            else:
                return 400, {"error": "Invalid method"}
            
            try:
                response_data = response.json()
            except:
                response_data = {"message": response.text}
            
            return response.status_code, response_data
            
    except Exception as e:
        return 500, {"error": str(e)}

async def create_github_repo(repo_name: str, description: str = "", private: bool = False) -> str:
    status, result = await github_api_request("POST", "user/repos", {
        "name": repo_name,
        "description": description,
        "private": private,
        "auto_init": True
    })
    
    if status == 201:
        repo_data = result
        return f"""## ✅ Repository Created Successfully!

**Repository:** {repo_data['name']}
**URL:** {repo_data['html_url']}
**Private:** {repo_data['private']}

You can now clone it with:
```bash
git clone {repo_data['clone_url']}
```"""
    elif status == 401:
        return f"❌ GitHub token not configured properly"
    elif status == 422:
        return f"❌ Repository '{repo_name}' already exists or name is invalid."
    else:
        error_msg = result.get('message', result.get('error', 'Unknown error'))
        return f"❌ Failed to create repository: {error_msg}"

async def list_github_repos() -> str:
    status, result = await github_api_request("GET", "user/repos?per_page=100&sort=updated&direction=desc")
    
    if status == 200:
        repos = result
        if not repos or len(repos) == 0:
            return "📁 No repositories found."
        
        output = "## 📁 Your GitHub Repositories\n\n"
        for repo in repos:
            name = repo.get('name', 'Unknown')
            description = repo.get('description', '')
            url = repo.get('html_url', '#')
            stars = repo.get('stargazers_count', 0)
            forks = repo.get('forks_count', 0)
            language = repo.get('language', 'Unknown')
            private = repo.get('private', False)
            
            privacy_icon = "🔒" if private else "🌍"
            output += f"### {privacy_icon} **{name}**\n"
            if description:
                output += f"  _{description[:100]}_\n"
            output += f"  📝 Language: {language}\n"
            output += f"  ⭐ Stars: {stars} | 🍴 Forks: {forks}\n"
            output += f"  🔗 {url}\n\n"
        return output
    else:
        return f"❌ Failed to fetch repositories"

# ── Zapier Helper ─────────────────────────────────────────────────────────────
async def _zapier_text(method: str, params: dict) -> str:
    """Call Zapier MCP and return text response"""
    if not ZAPIER_TOKEN:
        return "❌ Zapier token missing. Add ZAPIER_TOKEN to .env file"
    
    try:
        # Use the token as a URL parameter
        url = f"https://mcp.zapier.com/api/v1/connect?token={ZAPIER_TOKEN}"
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
        
        # Handle SSE response
        if "text/event-stream" in response.headers.get("content-type", ""):
            for line in response.text.strip().splitlines():
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw and raw != "[DONE]":
                        try:
                            data = json.loads(raw)
                            result = data.get("result", {})
                            if isinstance(result, dict):
                                content = result.get("content", [])
                                if content:
                                    for item in content:
                                        if isinstance(item, dict) and "text" in item:
                                            return item["text"]
                        except:
                            pass
            return "✅ Action completed!"
        
        # Handle JSON response
        data = response.json()
        error = data.get("error")
        if error:
            return f"❌ Zapier error: {error.get('message', str(error))}"
        
        result = data.get("result", {})
        if isinstance(result, dict):
            content = result.get("content", [])
            if content:
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        return item["text"]
        
        return "✅ Done!"
        
    except httpx.TimeoutException:
        return "⏰ Request timeout. Please try again."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ── Tool runners ───────────────────────────────────────────────────────────────
async def run_tool_async(name: str, user_msg: str) -> str:

    if name == "get_current_datetime":
        now = datetime.datetime.now()
        return f"## 🕐 Current Date & Time\n\n**Date:** {now.strftime('%A, %B %d, %Y')}\n\n**Time:** {now.strftime('%I:%M:%S %p')}"

    # ── CREATE GITHUB REPOSITORY ───────────────────────────────────────────────
    if name == "github_create_repo":
        repo_match = re.search(r'(?:repo|repository|reposteries)\s+(?:called|named)?\s*["\']?([a-zA-Z0-9\-_]+)["\']?', user_msg, re.IGNORECASE)
        if not repo_match:
            repo_match = re.search(r'(?:create|new)\s+(?:repo|repository|reposteries)\s+(?:called|named)?\s*["\']?([a-zA-Z0-9\-_]+)["\']?', user_msg, re.IGNORECASE)
        
        repo_name = repo_match.group(1) if repo_match else None
        
        if not repo_name:
            words = user_msg.split()
            for word in reversed(words):
                if word and not word.lower() in ['create', 'new', 'a', 'repo', 'repository', 'reposteries', 'called', 'named', 'make']:
                    repo_name = word.strip('"\'')
                    break
        
        if not repo_name:
            return "❓ **Please specify a repository name.**\n\nExample: `create repository called test-1`"
        
        desc_match = re.search(r'(?:with description|desc):\s*(.+)', user_msg, re.IGNORECASE)
        description = desc_match.group(1) if desc_match else ""
        
        private = "private" in user_msg.lower()
        
        return await create_github_repo(repo_name, description, private)

    # ── LIST GITHUB REPOSITORIES ───────────────────────────────────────────────
    if name == "github_list_repos":
        return await list_github_repos()

    # ── DATABASE QUERIES ───────────────────────────────────────────────────────
    if name == "query_database":
        m = user_msg.lower()
        
        if any(k in m for k in ["employee", "staff", "who", "people", "workers"]):
            result = query_db("SELECT * FROM employees")
            try:
                import ast
                data = ast.literal_eval(result)
                if isinstance(data, list) and len(data) > 0:
                    output = "## 👥 Employees\n\n"
                    output += "| ID | Name | Role | Department |\n"
                    output += "|----|------|------|------------|\n"
                    for row in data:
                        output += f"| {row.get('id', '')} | {row.get('name', '')} | {row.get('role', '')} | {row.get('department', '')} |\n"
                    return output
            except:
                return result
        if "project" in m:
            result = query_db("SELECT * FROM projects")
            try:
                import ast
                data = ast.literal_eval(result)
                if isinstance(data, list) and len(data) > 0:
                    output = "## 📋 Projects\n\n"
                    output += "| ID | Name | Status | Team |\n"
                    output += "|----|------|--------|------|\n"
                    for row in data:
                        output += f"| {row.get('id', '')} | {row.get('name', '')} | {row.get('status', '')} | {row.get('team', '')} |\n"
                    return output
            except:
                return result
        return "Please specify 'employees' or 'projects'"

    # ── CALCULATIONS ───────────────────────────────────────────────────────────
    if name == "calculate":
        exprs = re.findall(r'[\d\+\-\*\/\.\(\)\s]+', user_msg)
        for e in exprs:
            e = e.strip()
            if len(e) > 1 and any(c in e for c in '+-*/'):
                try:
                    tree = ast.parse(e, mode='eval')
                    result = safe_eval(tree.body)
                    if isinstance(result, float) and result == int(result):
                        result = int(result)
                    return f"## 🧮 Calculation\n\n**{e.strip()} = {result}**"
                except: 
                    continue
        return None

    # ── SEND EMAIL (Zapier) ────────────────────────────────────────────────────
    if name == "zapier_email_send":
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_msg)
        to = match.group(0) if match else ""
        
        if not to:
            return "❌ No email address found."
        
        body = user_msg
        for marker in ["saying ", "that says ", "with message "]:
            idx = user_msg.lower().find(marker)
            if idx != -1:
                body = user_msg[idx + len(marker):].strip()
                break
        
        if body == user_msg and to:
            email_idx = user_msg.lower().find(to.lower())
            if email_idx != -1:
                after_email = user_msg[email_idx + len(to):].strip()
                if after_email:
                    for sep in ["saying", "that says", ":", "-"]:
                        if after_email.lower().startswith(sep):
                            after_email = after_email[len(sep):].strip()
                            break
                    body = after_email if after_email else body
        
        subject = "Message from Awura AI"
        subj_match = re.search(r'subject[:\s]+(.+?)(?:\s+body|\s+saying|$)', user_msg, re.IGNORECASE)
        if subj_match:
            subject = subj_match.group(1).strip()
        
        result = await _zapier_text("tools/call", {
            "name": "execute_zapier_write_action",
            "arguments": {
                "selected_api": "GoogleMailV2CLIAPI",
                "action": "message",
                "instructions": f"Send an email to {to} with subject '{subject}' and body: {body}",
                "output": "Confirm the action was completed and summarize the result.",
                "params": {
                    "to": to,
                    "subject": subject,
                    "body": body
                }
            }
        })
        
        if "success" in str(result).lower() or "sent" in str(result).lower():
            return f"✅ Email sent successfully to {to}!"
        return f"📧 Email result: {result}"

    # ── GITHUB ACTIONS (Zapier) ───────────────────────────────────────────────────
    if name == "zapier_github":
        m = user_msg.lower()

        if "create issue" in m:
            title_match = re.search(r'(?:titled|called|named|about)\s+(.+)', user_msg, re.IGNORECASE)
            title = title_match.group(1) if title_match else user_msg
            
            result = await _zapier_text("tools/call", {
                "name": "execute_zapier_write_action",
                "arguments": {
                    "selected_api": "GitHubCLIAPI",
                    "action": "issue",
                    "instructions": f"Create issue: {title}",
                    "output": "Confirm issue created.",
                    "params": {"title": title}
                }
            })
            return result

        if "create branch" in m:
            name_match = re.search(r'(?:called|named|say)\s+(\S+)', user_msg, re.IGNORECASE)
            branch = name_match.group(1) if name_match else "new-branch"
            
            result = await _zapier_text("tools/call", {
                "name": "execute_zapier_write_action",
                "arguments": {
                    "selected_api": "GitHubCLIAPI",
                    "action": "create_branch",
                    "instructions": f"Create branch {branch}",
                    "output": "Confirm branch created.",
                    "params": {"branch": branch}
                }
            })
            return result

        if "create gist" in m:
            description = "Created via Awura AI"
            content = user_msg
            desc_match = re.search(r'(?:titled|called|about)\s+(.+)', user_msg, re.IGNORECASE)
            if desc_match:
                description = desc_match.group(1)
            
            result = await _zapier_text("tools/call", {
                "name": "execute_zapier_write_action",
                "arguments": {
                    "selected_api": "GitHubCLIAPI",
                    "action": "gist",
                    "instructions": f"Create gist: {description}",
                    "output": "Confirm gist created.",
                    "params": {"description": description, "files": {"file.txt": {"content": content}}}
                }
            })
            return result

        repo_match = re.search(r'(?:repo|repository)\s+(?:called|named)?\s*(\S+)', user_msg, re.IGNORECASE)
        if repo_match:
            repo_name = repo_match.group(1)
            result = await _zapier_text("tools/call", {
                "name": "execute_zapier_read_action",
                "arguments": {
                    "selected_api": "GitHubCLIAPI",
                    "action": "repository_v2",
                    "instructions": f"Find repository {repo_name}",
                    "output": "Return repository info.",
                    "params": {"name": repo_name}
                }
            })
            return result

        return """## 🔧 GitHub Commands

**Repository Management:**
• `create repository called NAME` - Create a new repo
• `list all repos` - Show all your repositories
• `find repository called NAME` - Find a specific repo

**Issues & Branches:**
• `create issue titled TITLE` - Create a new issue
• `create branch named NAME` - Create a new branch
• `create gist` - Create a GitHub gist"""

    return None

# ── FastAPI App Setup ─────────────────────────────────────────────────────────
app = FastAPI(title="Awura AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    init_db()

app.mount("/static", StaticFiles(directory=".", html=True), name="static")

class ChatRequest(BaseModel):
    model: str
    messages: List[dict]
    file_names: List[str] = []
    session_id: str

class HistorySaveRequest(BaseModel):
    session_id: str
    title: str
    messages: str

@app.get("/")
async def root():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/models")
async def get_models():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:11434/api/tags", timeout=5)
            if r.status_code == 200:
                data = r.json()
                models = [m["name"] for m in data.get("models", [])]
                return {"models": models}
    except:
        pass
    return {"models": ["qwen2.5:1.5b", "llama3.2:3b", "mistral:7b"]}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename
    chars = save_file(filename, content)
    return {"filename": filename, "chars": chars}

@app.delete("/upload/{filename}")
async def delete_uploaded_file(filename: str):
    remove_file(filename)
    return {"status": "deleted"}

@app.get("/history")
async def get_history():
    return get_all_chats()

@app.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    messages = get_chat(session_id)
    if messages:
        return {"messages": messages}
    raise HTTPException(status_code=404, detail="Chat not found")

@app.post("/history/save")
async def save_chat_history(req: HistorySaveRequest):
    save_chat(req.session_id, req.title, req.messages)
    return {"status": "saved"}

@app.delete("/history/{session_id}")
async def delete_chat_history(session_id: str):
    delete_chat(session_id)
    return {"status": "deleted"}

@app.post("/chat")
async def chat(req: ChatRequest):
    async def generate():
        user_msg = req.messages[-1]["content"] if req.messages else ""
        
        tool = detect_tool(user_msg)
        if tool:
            try:
                tool_result = await run_tool_async(tool, user_msg)
                if tool_result:
                    yield f"data: {json.dumps({'type': 'tool', 'tool': tool, 'result': tool_result[:1000]})}\n\n"
                    yield f"data: {json.dumps({'type': 'token', 'content': tool_result})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    return
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': f'Error: {str(e)}'})}\n\n"
                return
        
        if req.file_names:
            file_context = get_file_context(req.file_names)
            if file_context:
                user_msg = f"Context from files:\n{file_context}\n\nUser: {user_msg}"
                req.messages[-1]["content"] = user_msg
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    "http://localhost:11434/api/generate",
                    json={
                        "model": req.model,
                        "prompt": req.messages[-1]["content"],
                        "stream": True
                    }
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    yield f"data: {json.dumps({'type': 'token', 'content': data['response']})}\n\n"
                                if data.get("done"):
                                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                            except:
                                pass
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)