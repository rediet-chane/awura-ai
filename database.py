import sqlite3

DB_PATH = "awura.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY, name TEXT, role TEXT, department TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY, name TEXT, status TEXT, team TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        title TEXT,
        messages TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    if not conn.execute("SELECT 1 FROM employees LIMIT 1").fetchone():
        conn.executemany("INSERT INTO employees VALUES (?,?,?,?)", [
            (1, "Redie",  "AI Engineer", "Tech"),
            (2, "Amir",   "Manager",     "Tech"),
            (3, "Sara",   "Designer",    "Product"),
            (4, "Dawit",  "Developer",   "Tech"),
            (5, "Meron",  "Analyst",     "Data"),
        ])

    if not conn.execute("SELECT 1 FROM projects LIMIT 1").fetchone():
        conn.executemany("INSERT INTO projects VALUES (?,?,?,?)", [
            (1, "Awura AI Assistant", "Active",    "Tech"),
            (2, "Mobile App",         "Planning",  "Product"),
            (3, "Data Pipeline",      "Active",    "Data"),
        ])

    conn.commit()
    conn.close()

def query_db(sql: str):
    if not sql.strip().upper().startswith("SELECT"):
        return "Only SELECT queries are allowed."
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(sql).fetchall()
        cols = [d[0] for d in conn.execute(sql).description]
        conn.close()
        if not rows:
            return "No results found."
        result = [dict(zip(cols, row)) for row in rows]
        return str(result)
    except Exception as e:
        return f"Database error: {e}"

def save_chat(session_id: str, title: str, messages: str):
    conn = sqlite3.connect(DB_PATH)
    existing = conn.execute(
        "SELECT id FROM chat_history WHERE session_id=?", (session_id,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE chat_history SET messages=?, title=? WHERE session_id=?",
            (messages, title, session_id)
        )
    else:
        conn.execute(
            "INSERT INTO chat_history (session_id, title, messages) VALUES (?,?,?)",
            (session_id, title, messages)
        )
    conn.commit()
    conn.close()

def get_all_chats():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT session_id, title, created_at FROM chat_history ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]

def get_chat(session_id: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT messages FROM chat_history WHERE session_id=?", (session_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None

def delete_chat(session_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM chat_history WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()