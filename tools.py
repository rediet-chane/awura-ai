import datetime, re, httpx, json, ast, operator, os
from dotenv import load_dotenv
from database import query_db

load_dotenv()

TOKEN = os.getenv("ZAPIER_TOKEN")
ZAPIER_URL = "https://mcp.zapier.com/api/v1/connect"

# ── Exact tool names from Zapier (discovered via list_enabled_zapier_actions) ─
GMAIL_API  = "GoogleMailV2CLIAPI"
GITHUB_API = "GitHubCLIAPI"

# Gmail tools
GMAIL_SEND         = "gmail_send_email"
GMAIL_FIND         = "gmail_find_email"
GMAIL_DRAFT        = "gmail_create_draft"

# GitHub tools
GITHUB_FIND_REPO   = "github_find_repository"
GITHUB_CREATE_ISSUE= "github_create_issue"
GITHUB_FIND_ISSUE  = "github_find_issue"
GITHUB_CREATE_BRANCH = "github_create_branch"
GITHUB_FIND_BRANCH = "github_find_branch"
GITHUB_CREATE_GIST = "github_create_gist"

OPS = {ast.Add:operator.add, ast.Sub:operator.sub, ast.Mult:operator.mul,
       ast.Div:operator.truediv, ast.Pow:operator.pow, ast.Mod:operator.mod}

def safe_eval(node):
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -safe_eval(node.operand)
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    raise ValueError("Invalid")

# ── Tool detection ─────────────────────────────────────────────────────────────
TOOLS = [
    {"name": "get_current_datetime", "keywords": ["time","date","today","now","what day","what time","clock","hour","minute"]},
    {"name": "query_database",       "keywords": ["employee","project","team","staff","database","department","show all","list all","who works","members"]},
    {"name": "calculate",            "keywords": ["calculate","compute","math","sum","multiply","divide","plus","minus","times","squared","percent","how much is"]},
    {"name": "zapier_email",         "keywords": ["send email","email to","mail to","write email","send message to","saying","@gmail","@yahoo","@outlook","@hotmail"]},
    {"name": "zapier_github",        "keywords": ["github","repository","repo","my repo","see repo","list repo","create repo","find repo","issue","pull request","branch","gist"]},
    {"name": "zapier_list",          "keywords": ["zapier tools","my zapier","list zapier","what can zapier","zapier actions","available tools","enabled actions"]},
]

def detect_tool(msg: str):
    m = msg.lower().strip()
    if re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', msg):
        return "zapier_email"
    for t in TOOLS:
        if any(kw in m for kw in sorted(t["keywords"], key=len, reverse=True)):
            return t["name"]
    return None

# ── Zapier API caller ──────────────────────────────────────────────────────────
def _zapier(method: str, params: dict) -> str:
    if not TOKEN:
        return "Zapier token missing. Add ZAPIER_TOKEN to your .env file."
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/json, text/event-stream",
        }
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        r = httpx.post(ZAPIER_URL, json=payload, headers=headers, timeout=20)
        ct = r.headers.get("content-type", "")

        # SSE stream
        if "text/event-stream" in ct:
            collected = []
            for line in r.text.strip().splitlines():
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw and raw != "[DONE]":
                        try:
                            obj = json.loads(raw)
                            res = obj.get("result", {})
                            if isinstance(res, dict):
                                content = res.get("content", [])
                                if content:
                                    collected.append(content[0].get("text",""))
                        except: collected.append(raw)
            return "\n".join(collected).strip() or "Done."

        data = r.json()
        err = data.get("error")
        if err:
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return f"Zapier error: {msg}"

        result = data.get("result", {})
        if isinstance(result, str):
            try: result = json.loads(result)
            except: return result

        if isinstance(result, dict):
            content = result.get("content", [])
            if content:
                return "\n".join(c.get("text","") for c in content if isinstance(c,dict)).strip()
            tools = result.get("tools", [])
            if tools:
                return "\n".join(f"• {t.get('name','')}" for t in tools)
            return json.dumps(result, indent=2)
        return str(result) or "Done."

    except httpx.TimeoutException:
        return "Zapier timeout — check your internet."
    except Exception as e:
        return f"Zapier error: {e}"

def _write(tool_name: str, instructions: str, params: dict) -> str:
    return _zapier("tools/call", {
        "name": "execute_zapier_write_action",
        "arguments": {
            "tool_name": tool_name,
            "instructions": instructions,
            "output": "Confirm the action was completed and summarize the result.",
            "params": params
        }
    })

def _read(tool_name: str, instructions: str, params: dict) -> str:
    return _zapier("tools/call", {
        "name": "execute_zapier_read_action",
        "arguments": {
            "tool_name": tool_name,
            "instructions": instructions,
            "output": "Return the data found in a readable format.",
            "params": params
        }
    })

# ── Tool runners ───────────────────────────────────────────────────────────────
def run_tool(name: str, user_msg: str) -> str:

    if name == "get_current_datetime":
        return datetime.datetime.now().strftime("Date: %A, %B %d, %Y | Time: %I:%M:%S %p")

    if name == "query_database":
        m = user_msg.lower()
        if any(k in m for k in ["employee","staff","who","team","person","people","workers"]):
            return query_db("SELECT * FROM employees")
        if "project" in m:
            return query_db("SELECT * FROM projects")
        return query_db("SELECT * FROM employees") + "\n\n" + query_db("SELECT * FROM projects")

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
                    return f"{e.strip()} = {result}"
                except: continue
        return "No valid math expression found."

    if name == "zapier_list":
        return _zapier("tools/call", {
            "name": "list_enabled_zapier_actions",
            "arguments": {}
        })

    # ── EMAIL ──────────────────────────────────────────────────────────────────
    if name == "zapier_email":
        match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', user_msg)
        to = match.group(0) if match else ""

        body = user_msg
        for marker in ["saying ", "that says ", "with message ", "body: ", "message: "]:
            idx = user_msg.lower().find(marker)
            if idx != -1:
                body = user_msg[idx + len(marker):].strip()
                break

        subject = "Message from Awura AI"
        subj_match = re.search(r'subject[:\s]+(.+?)(?:\s+body|\s+saying|$)', user_msg, re.IGNORECASE)
        if subj_match:
            subject = subj_match.group(1).strip()

        return _write(
            GMAIL_SEND,
            f"Send an email to {to} with subject '{subject}' and body: {body}",
            {"to": to, "subject": subject, "body": body}
        )

    # ── GITHUB ─────────────────────────────────────────────────────────────────
    if name == "zapier_github":
        m = user_msg.lower()

        if any(k in m for k in ["create issue","new issue"]):
            title_match = re.search(r'(?:titled|called|named|about)\s+(.+)', user_msg, re.IGNORECASE)
            title = title_match.group(1) if title_match else user_msg
            return _write(GITHUB_CREATE_ISSUE, f"Create a GitHub issue: {title}", {"title": title})

        if any(k in m for k in ["create branch","new branch"]):
            name_match = re.search(r'(?:called|named|say)\s+(\S+)', user_msg, re.IGNORECASE)
            branch = name_match.group(1) if name_match else "new-branch"
            return _write(GITHUB_CREATE_BRANCH, f"Create a branch named {branch}", {"branch": branch})

        if any(k in m for k in ["create gist","new gist"]):
            return _write(GITHUB_CREATE_GIST, f"Create a GitHub gist: {user_msg}", {})

        if any(k in m for k in ["find issue","search issue"]):
            return _read(GITHUB_FIND_ISSUE, user_msg, {})

        if any(k in m for k in ["find branch","search branch"]):
            return _read(GITHUB_FIND_BRANCH, user_msg, {})

        # Default: find repository
        name_match = re.search(r'(?:repo|repository)\s+(?:called|named)?\s*(\S+)', user_msg, re.IGNORECASE)
        repo = name_match.group(1) if name_match else ""
        return _read(
            GITHUB_FIND_REPO,
            f"Find my GitHub repositories" + (f" named {repo}" if repo else ""),
            {"name": repo} if repo else {}
        )

    return "Unknown tool."

def zapier_list_tools() -> str:
    return run_tool("zapier_list", "")