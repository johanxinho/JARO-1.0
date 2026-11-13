import sqlite3, json
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / "JohanAI/workspace/jaro_memory.db"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS activity_logs USING fts5(fecha, proyecto, tipo, tarea, resultado, archivos)")
        conn.execute("CREATE TABLE IF NOT EXISTS skill_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT, skill_name TEXT, tarea_origen TEXT, parametros TEXT, estado TEXT, salida TEXT)")

def log_activity(proyecto, tipo, tarea, resultado="", archivos=None):
    init_db()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO activity_logs VALUES (?, ?, ?, ?, ?, ?)", (fecha, proyecto, tipo, tarea, str(resultado)[:1500], json.dumps(archivos or [])))

def search_memory(query, limit=5):
    init_db()
    clean_q = " OR ".join([w for w in query.replace('"', "").split() if len(w) > 2])
    if not clean_q: return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM activity_logs WHERE activity_logs MATCH ? ORDER BY rank LIMIT ?", (clean_q, limit))
        return [dict(r) for r in cur.fetchall()]

def log_skill_execution(skill_name, tarea_origen, parametros, estado, salida):
    init_db()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO skill_logs (fecha, skill_name, tarea_origen, parametros, estado, salida) VALUES (?, ?, ?, ?, ?, ?)", (fecha, skill_name, tarea_origen, json.dumps(parametros), estado, str(salida)[:1000]))

def get_skill_history(limit=15):
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute("SELECT * FROM skill_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
