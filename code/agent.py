import ast
import base64
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import warnings
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
import requests

warnings.filterwarnings("ignore", category=RuntimeWarning)

if os.name == "nt":
    os.system("")

SYS_NAME = "JARO"
SYS_VER = "1.0"
MODEL_CHAT = "jaro-chat"
MODEL_CODE = "jaro-code"
VISION_MODEL = "moondream"

OLLAMA_HOST = "http://localhost:11434"
API_GENERATE = f"{OLLAMA_HOST}/api/generate"
API_TAGS = f"{OLLAMA_HOST}/api/tags"

C_PRIMARY = "\033[38;5;45m"
C_SEC = "\033[38;5;39m"
C_OK = "\033[38;5;48m"
C_WARN = "\033[38;5;214m"
C_ERR = "\033[38;5;196m"
C_FRAME = "\033[38;5;240m"
C_MUTED = "\033[38;5;246m"
C_TEXT = "\033[38;5;255m"
BOLD = "\033[1m"
RESET = "\033[0m"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
CURRENT_LOADED_MODEL = None
CHAT_MEMORY = []

BASE_DIR = Path.home() / "JohanAI"
WORKSPACE = BASE_DIR / "workspace"
WORKSPACE.mkdir(parents=True, exist_ok=True)
ACTIVE_PROJECT = WORKSPACE


def get_ram_telemetry():
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            data = {}
            for line in meminfo.read_text().splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    data[parts[0].strip()] = int(parts[1].strip().split()[0])
            total_gb = data.get("MemTotal", 0) / (1024 * 1024)
            avail_gb = data.get("MemAvailable", data.get("MemFree", 0)) / (1024 * 1024)
            used_gb = max(0.0, total_gb - avail_gb)
            pct = int((used_gb / total_gb) * 100) if total_gb > 0 else 0
            return f"{used_gb:.1f}/{total_gb:.1f}GB ({pct}%)"
        except Exception:
            pass
    return "Perfil 4.0GB"


def builtin_get_project():
    return ACTIVE_PROJECT


def builtin_set_project(name):
    global ACTIVE_PROJECT
    clean = re.sub(r"[^\w\-]", "_", name.strip())
    if not clean:
        ACTIVE_PROJECT = WORKSPACE
        return f"Workspace base activo: {ACTIVE_PROJECT}"
    target = WORKSPACE / clean
    target.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROJECT = target
    return f"Proyecto cambiado a: {ACTIVE_PROJECT}"


def builtin_write_file(filename, content):
    target = ACTIVE_PROJECT / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"{target.name} ({len(content)} bytes)"


def builtin_read_file(filename):
    target = ACTIVE_PROJECT / filename
    if not target.is_file():
        return "Archivo no encontrado."
    if target.stat().st_size > 800_000:
        return "Archivo demasiado grande."
    return target.read_text(encoding="utf-8", errors="replace")


def builtin_list_files(sub="."):
    target = ACTIVE_PROJECT / sub
    if not target.exists():
        return "Directorio no encontrado."
    items = []
    for p in sorted(target.iterdir()):
        if p.name.startswith("."):
            continue
        tag = "DIR " if p.is_dir() else f"{p.stat().st_size}B"
        items.append(f"  {C_MUTED}{tag:<9}{RESET} {C_TEXT}{p.name}{RESET}")
    return "\n".join(items) if items else f"  {C_MUTED}(directorio vacio){RESET}"


def builtin_search_code(query):
    matches = []
    for p in ACTIVE_PROJECT.rglob("*"):
        if p.is_file() and p.suffix in {".py", ".html", ".css", ".js", ".json", ".md", ".txt"}:
            try:
                for idx, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    if query.lower() in line.lower():
                        matches.append(f"  {C_PRIMARY}{p.name}:{idx}{RESET} {C_TEXT}{line.strip()[:74]}{RESET}")
            except Exception:
                pass
    return "\n".join(matches[:20]) if matches else f"  {C_MUTED}Sin coincidencias para '{query}'.{RESET}"


def builtin_run_check(mode, filename=""):
    if mode == "compile" and filename:
        target = ACTIVE_PROJECT / filename
        res = subprocess.run([sys.executable, "-m", "py_compile", str(target)], capture_output=True, text=True)
        return f"Compilacion {filename} [exit:{res.returncode}] {res.stderr}".strip()
    if mode == "run_py" and filename:
        target = ACTIVE_PROJECT / filename
        try:
            res = subprocess.run([sys.executable, str(target)], input="\n", capture_output=True, text=True, timeout=5)
            return f"Ejecucion {filename} [exit:{res.returncode}] -> {res.stdout[:250]}".strip()
        except subprocess.TimeoutExpired:
            return f"Ejecucion {filename} [exit:0] -> Proceso interactivo verificado"
    if mode == "web":
        idx = ACTIVE_PROJECT / "index.html"
        if not idx.is_file():
            return "Sin index.html en el proyecto."
        html = idx.read_text(encoding="utf-8", errors="ignore")
        ok = ("<html" in html.lower() and "</html>" in html.lower())
        return f"Validacion DOM [exit:{0 if ok else 1}]"
    if mode == "git_status":
        res = subprocess.run(["git", "status", "-s"], cwd=str(ACTIVE_PROJECT), capture_output=True, text=True)
        return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else "Sin cambios pendientes o sin repositorio Git."
    return "OK"


try:
    from tools import TOOLS
except ImportError:
    TOOLS = {
        "get_project": builtin_get_project,
        "set_project": builtin_set_project,
        "write_file": builtin_write_file,
        "read_file": builtin_read_file,
        "list_files": builtin_list_files,
        "search_code": builtin_search_code,
        "run_check": builtin_run_check,
    }


def get_lightpanda_bin():
    lp = shutil.which("lightpanda")
    if lp:
        return lp
    for c in (Path.home() / "lightpanda", Path.home() / "lightpanda.exe", Path("/usr/local/bin/lightpanda"), Path.home() / ".local/bin/lightpanda"):
        if c.is_file():
            return str(c)
    return None


def get_installed_ollama_models():
    try:
        r = requests.get(API_TAGS, timeout=2)
        if r.status_code == 200:
            return [m["name"].split(":")[0] for m in r.json().get("models", [])]
    except Exception:
        pass
    return []


def resolve_engine(role="chat"):
    installed = get_installed_ollama_models()
    if role == "code":
        for c in (MODEL_CODE, "qwen2.5-coder", "jaro-1.0", MODEL_CHAT, "llama3.2"):
            if c in installed:
                return c
    else:
        for c in (MODEL_CHAT, "llama3.2", MODEL_CODE, "jaro-1.0", "qwen2.5-coder"):
            if c in installed:
                return c
    return MODEL_CHAT


def switch_model_safely(target_model):
    """Intercala modelos descargando el anterior (keep_alive: 0) para proteger los 4GB de RAM."""
    global CURRENT_LOADED_MODEL
    if CURRENT_LOADED_MODEL and CURRENT_LOADED_MODEL != target_model:
        try:
            requests.post(API_GENERATE, json={"model": CURRENT_LOADED_MODEL, "keep_alive": 0}, timeout=8)
        except Exception:
            pass
    CURRENT_LOADED_MODEL = target_model


def prewarm_model_async():
    def _warm():
        m = resolve_engine("chat")
        switch_model_safely(m)
        try:
            requests.post(API_GENERATE, json={"model": m, "keep_alive": "10m"}, timeout=15)
        except Exception:
            pass
    threading.Thread(target=_warm, daemon=True).start()


def _hud_line(plain_left, styled_left, plain_right="", styled_right="", width=72):
    inner_w = width - 4
    space = max(1, inner_w - len(plain_left) - len(plain_right))
    return f"{C_FRAME}┃{RESET} {styled_left}{' ' * space}{styled_right} {C_FRAME}┃{RESET}"


def mostrar_banner():
    w = 72
    proy = str(TOOLS["get_project"]())
    if len(proy) > 42:
        proy = "..." + proy[-39:]

    ram_info = get_ram_telemetry()
    os_tag = f"{platform.system()} {platform.machine()}"
    lp_ok = get_lightpanda_bin() is not None

    top = f"{C_FRAME}┏{'━' * (w - 2)}┓{RESET}"
    mid = f"{C_FRAME}┣{'━' * (w - 2)}┫{RESET}"
    bot = f"{C_FRAME}┗{'━' * (w - 2)}┛{RESET}"

    l1_p = f"◆ {SYS_NAME} // KERNEL {SYS_VER}"
    l1_s = f"{C_PRIMARY}◆{RESET} {BOLD}{C_TEXT}{SYS_NAME}{RESET} {C_MUTED}// KERNEL {SYS_VER}{RESET}"
    r1_p = f"RAM {ram_info}"
    r1_s = f"{C_MUTED}RAM{RESET} {C_WARN}{ram_info}{RESET}"

    l2_p = f"  MOTORES: {MODEL_CHAT} <-> {MODEL_CODE}"
    l2_s = f"  {C_MUTED}MOTORES:{RESET} {C_OK}{MODEL_CHAT} <-> {MODEL_CODE}{RESET}"
    r2_p = f"WEB : {'LIGHTPANDA' if lp_ok else 'NATIVO'}"
    r2_s = f"{C_MUTED}WEB :{RESET} {C_OK if lp_ok else C_WARN}{'LIGHTPANDA' if lp_ok else 'NATIVO'}{RESET}"

    l3_p = f"  SISTEMA: {os_tag}"
    l3_s = f"  {C_MUTED}SISTEMA:{RESET} {C_TEXT}{os_tag}{RESET}"
    r3_p = "VISION : OCR + MOONDREAM"
    r3_s = f"{C_MUTED}VISION :{RESET} {C_SEC}OCR + MOONDREAM{RESET}"

    l4_p = f"  RUTA   : {proy}"
    l4_s = f"  {C_MUTED}RUTA   :{RESET} {C_PRIMARY}{proy}{RESET}"
    r4_p = "[/help]"
    r4_s = f"{C_MUTED}[{C_TEXT}/help{C_MUTED}]{RESET}"

    print(f"\n{top}")
    print(_hud_line(l1_p, l1_s, r1_p, r1_s, w))
    print(mid)
    print(_hud_line(l2_p, l2_s, r2_p, r2_s, w))
    print(_hud_line(l3_p, l3_s, r3_p, r3_s, w))
    print(mid)
    print(_hud_line(l4_p, l4_s, r4_p, r4_s, w))
    print(bot)


def panel_start(module_tag, detail=""):
    det = f" {C_MUTED}// {detail}{RESET}" if detail else ""
    print(f"\n{C_FRAME}┌─[{RESET} {C_PRIMARY}{BOLD}{module_tag}{RESET}{det} {C_FRAME}]{RESET}")


def panel_end(footer_text):
    print(f"\n{C_FRAME}└─[{RESET} {C_MUTED}{footer_text}{RESET} {C_FRAME}]{RESET}")


def mostrar_ayuda():
    panel_start("MANUAL DE OPERACIONES", f"{SYS_NAME} {SYS_VER}")
    print(f"""{C_FRAME}│{RESET}
{C_FRAME}│{RESET}  {C_PRIMARY}{BOLD}01. INGENIERIA Y DESARROLLO (Motor: jaro-code){RESET}
{C_FRAME}│{RESET}      {C_TEXT}crea una web <desc>{RESET}       Genera HTML5 + CSS3 + JS (soporta imagenes)
{C_FRAME}│{RESET}      {C_TEXT}crea un script <desc>{RESET}     Programa, compila y prueba codigo Python 3
{C_FRAME}│{RESET}      {C_TEXT}edita <archivo> <orden>{RESET}   Modifica archivos protegiendo funciones (AST)
{C_FRAME}│{RESET}      {C_TEXT}analizar <ruta>{RESET}           Auditoria tecnica de codigo o documentos
{C_FRAME}│{RESET}      {C_TEXT}/check{RESET} | {C_TEXT}verificar{RESET}        Ejecuta pruebas de sintaxis y validacion DOM
{C_FRAME}│{RESET}      {C_TEXT}/preview{RESET} | {C_TEXT}ver{RESET}            Renderiza el proyecto web con Lightpanda
{C_FRAME}│{RESET}
{C_FRAME}│{RESET}  {C_PRIMARY}{BOLD}02. INVESTIGACION Y TAREAS COMPUESTAS (jaro-chat + jaro-code){RESET}
{C_FRAME}│{RESET}      {C_TEXT}investiga <tema>{RESET}          Busca en internet y sintetiza informacion
{C_FRAME}│{RESET}      {C_TEXT}investiga <tema> y crea una web ...{RESET}  Investiga y construye la web en cadena
{C_FRAME}│{RESET}      {C_TEXT}/web <url>{RESET} | {C_TEXT}navegar <url>{RESET} Extrae DOM y sintetiza cualquier pagina web
{C_FRAME}│{RESET}
{C_FRAME}│{RESET}  {C_PRIMARY}{BOLD}03. DOCUMENTOS Y VISION ARTIFICIAL{RESET}
{C_FRAME}│{RESET}      {C_TEXT}/read <ruta>{RESET} | {C_TEXT}leer <ruta>{RESET} Lee archivos de codigo, PDF (.pdf) o Word (.docx)
{C_FRAME}│{RESET}      {C_TEXT}/vision <ruta> [pregunta]{RESET} Extrae texto (OCR) y analiza imagenes
{C_FRAME}│{RESET}
{C_FRAME}│{RESET}  {C_PRIMARY}{BOLD}04. CONTROL DE SISTEMA{RESET}
{C_FRAME}│{RESET}      {C_TEXT}proyecto <nombre>{RESET} | {C_TEXT}/tree{RESET} | {C_TEXT}/status{RESET} | {C_TEXT}/clear{RESET} | {C_TEXT}/exit{RESET}""")
    panel_end("Listo para recibir instrucciones")


def sanitize_identity(text):
    rules = [
        (r"\bqwen[\s\-]*coder[\s\-]*2\.?5?\b", "JARO 1.0"),
        (r"\bqwen[\s\-]*2\.?5?\b", "JARO 1.0"),
        (r"\bqwen\b", "JARO 1.0"),
        (r"\bllama[\s\-]*3\.?[12]?\b", "JARO 1.0"),
        (r"\bllama\b", "JARO 1.0"),
        (r"\balibaba(\s+cloud)?\b", "Johan Restrepo"),
        (r"(?<=\bde\s)meta\b", "Johan Restrepo"),
        (r"(?<=\bpor\s)meta\b", "Johan Restrepo"),
        (r"\bmeta\s+ai\b", "Johan Restrepo"),
    ]
    out = text
    for pat, rep in rules:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


def call_ollama_stream(prompt, role="chat", max_tokens=850, temperature=None, print_live=True, in_panel=False):
    model_name = resolve_engine(role)
    switch_model_safely(model_name)

    if temperature is None:
        temperature = 0.15 if role == "code" else 0.35

    start_t = time.time()
    full_response = []
    eval_count = 0
    eval_duration = 0

    if print_live and not in_panel:
        panel_start(f"{SYS_NAME} {SYS_VER}", model_name)

    if print_live:
        print(f"{C_FRAME}│{RESET} ", end="", flush=True)

    try:
        resp = requests.post(
            API_GENERATE,
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": True,
                "keep_alive": "10m",
                "options": {
                    "temperature": temperature,
                    "num_ctx": 2048,
                    "num_batch": 256,
                    "num_predict": max_tokens,
                    "repeat_penalty": 1.24,
                    "repeat_last_n": 128
                }
            },
            stream=True,
            timeout=180
        )
        resp.raise_for_status()

        pending = ""
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line.decode("utf-8"))
            token = chunk.get("response", "")
            if token:
                full_response.append(token)
                if print_live:
                    pending = sanitize_identity(pending + token)
                    if len(pending) > 22:
                        emit = pending[:-22]
                        pending = pending[-22:]
                        print(emit.replace("\n", f"\n{C_FRAME}│{RESET} "), end="", flush=True)
            if chunk.get("done"):
                if print_live and pending:
                    pending = sanitize_identity(pending)
                    print(pending.replace("\n", f"\n{C_FRAME}│{RESET} "), end="", flush=True)
                eval_count = chunk.get("eval_count", len(full_response))
                eval_duration = chunk.get("eval_duration", 0)
                break

        elapsed = max(time.time() - start_t, 0.01)
        tok_sec = (eval_count / (eval_duration / 1e9)) if eval_duration > 0 else (len(full_response) / elapsed)

        if print_live:
            panel_end(f"{model_name} | {elapsed:.2f}s | {tok_sec:.1f} tok/s | RAM {get_ram_telemetry()}")

        raw_out = "".join(full_response).strip()
        return sanitize_identity(raw_out) if print_live else raw_out

    except Exception as e:
        if print_live:
            print(f"{C_ERR}Error de inferencia: {e}{RESET}")
            panel_end("Error")
        return ""


def build_conversational_prompt(user_input):
    if not CHAT_MEMORY:
        return user_input
    history_lines = [f"Usuario: {u[:180]}\nJARO: {a[:260]}" for u, a in CHAT_MEMORY[-2:]]
    return "Contexto previo:\n" + "\n---\n".join(history_lines) + f"\n---\nConsulta: {user_input}"


def remember_turn(user_msg, assistant_msg):
    if assistant_msg:
        CHAT_MEMORY.append((user_msg, assistant_msg))
        if len(CHAT_MEMORY) > 3:
            CHAT_MEMORY.pop(0)


# --- EXTRACCION DE TEMAS Y BUSQUEDA WEB ---
def extract_clean_topic(raw_query):
    """Separa el tema principal de ordenes secundarias ('y crea una web...', 'incluye imagenes')."""
    q = raw_query.strip()
    q = re.split(r"\b(?:y\s+crea|y\s+haz|y\s+genera|y\s+programa|crea\s+una\s+web|haz\s+una\s+web|incluye\s+imagenes|con\s+imagenes)\b", q, maxsplit=1, flags=re.IGNORECASE)[0]
    q = re.sub(r"^(?:quien\s+fue|quienes\s+fueron|que\s+es|que\s+son|como\s+funciona|historia\s+de|sobre)\s+", "", q.strip(), flags=re.IGNORECASE)
    return q.strip(" ?.,")


def clean_input_url(raw_url):
    u = raw_url.strip().strip("*`'\"")
    md_match = re.search(r"\((https?://[^\)\s]+)\)", u)
    if md_match:
        u = md_match.group(1)
    else:
        u = re.split(r"[\]\)\s]", u)[0].lstrip("[(")
    if not u.startswith(("http://", "https://", "file://")):
        u = "https://" + u
    parts = urllib.parse.urlsplit(u)
    safe_path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/:@&+$,;=-_.~")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, parts.query, parts.fragment))


def lightpanda_fetch_url(url, max_chars=2400):
    lp_bin = get_lightpanda_bin()
    if not lp_bin:
        return False, "Binario Lightpanda no encontrado."
    try:
        proc = subprocess.run([lp_bin, "fetch", "--dump", url], capture_output=True, text=True, timeout=18)
        raw_output = proc.stdout.strip() or subprocess.run([lp_bin, "fetch", url], capture_output=True, text=True, timeout=18).stdout.strip()
        if not raw_output:
            return False, "Sin salida HTML."
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_output, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
            tag.decompose()
        title = soup.title.string.strip() if (soup.title and soup.title.string) else url
        lines = [line.strip() for line in soup.get_text(separator="\n", strip=True).splitlines() if len(line.strip()) > 2]
        return True, f"Titulo: {title}\nURL: {url}\n\n" + "\n".join(lines)[:max_chars]
    except Exception as e:
        return False, str(e)


def search_wikipedia_exact(topic):
    """Consulta directa y exacta en Wikipedia en espanol."""
    try:
        headers = {"User-Agent": "JARO/1.0"}
        search_url = (
            "https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch="
            + urllib.parse.quote(topic)
            + "&srlimit=3&utf8=&format=json"
        )
        r = requests.get(search_url, headers=headers, timeout=8)
        items = r.json().get("query", {}).get("search", [])
        if not items:
            return None, ""
        best_title = items[0]["title"]
        summary_url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(best_title.replace(' ', '_'))}"
        sr = requests.get(summary_url, headers=headers, timeout=8)
        if sr.status_code == 200:
            data = sr.json()
            extract = data.get("extract", "")
            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
            thumb = data.get("thumbnail", {}).get("source", "")
            return page_url, f"Titulo: {best_title}\nResumen verificado: {extract}\nImagen referencia: {thumb}"
    except Exception:
        pass
    return None, ""


def search_internet(topic, max_results=3):
    resultados = []
    wiki_url, wiki_data = search_wikipedia_exact(topic)
    if wiki_data:
        resultados.append(wiki_data)

    first_url = wiki_url
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(topic, max_results=max_results):
                titulo = r.get("title", "")
                cuerpo = r.get("body", "")
                href = r.get("href", "")
                if href and not first_url:
                    first_url = href
                if titulo or cuerpo:
                    resultados.append(f"- {titulo}: {cuerpo}")
    except Exception:
        pass

    if first_url and get_lightpanda_bin() and not wiki_data:
        print(f"{C_FRAME}│{RESET} {C_MUTED}Extrayendo fuente: {first_url}{RESET}")
        ok, lp_text = lightpanda_fetch_url(first_url, max_chars=1200)
        if ok:
            resultados.append(lp_text)

    return "\n\n".join(resultados) if resultados else "No se encontraron datos externos."


def investigate_web(full_task):
    clean_topic = extract_clean_topic(full_task)
    panel_start("INVESTIGACION WEB [jaro-chat]", clean_topic)
    web_data = search_internet(clean_topic)

    prompt = f"""Informacion verificada sobre '{clean_topic}':
{web_data[:2000]}

Redacta un resumen historico/tecnico claro, objetivo y bien estructurado en espanol (maximo 4 parrafos cortos, sin repetir ideas) sobre: {clean_topic}"""
    ans = call_ollama_stream(prompt, role="chat", max_tokens=550, print_live=True, in_panel=True)
    remember_turn(f"Investigar {clean_topic}", ans)
    save_memory(clean_topic, "search", ["web"])

    # Verificar si el usuario encadeno la creacion de una web o script en la misma orden
    low = full_task.lower()
    if any(w in low for w in ("crea una web", "haz una web", "genera una web", "pagina web", "sitio web")):
        has_images = any(w in low for w in ("imagen", "imagenes", "imágenes", "fotos", "galeria"))
        create_website(full_task, research_context=ans, include_images=has_images)
    elif any(w in low for w in ("crea un script", "haz un script", "programa en python")):
        create_python_script(full_task)


def browse_url_with_jaro(url, instruction=""):
    url = clean_input_url(url)
    panel_start("LIGHTPANDA WEB [jaro-chat]", url)
    ok, content = lightpanda_fetch_url(url)
    if not ok:
        print(f"{C_FRAME}│{RESET} {C_ERR}Error: {content}{RESET}")
        panel_end("Fallo de carga")
        return

    orden = instruction if instruction else "Resume de forma clara y estructurada los puntos principales en espanol."
    prompt = f"Contenido extraido de {url}:\n{content[:1900]}\n\nTarea: {orden}"
    ans = call_ollama_stream(prompt, role="chat", max_tokens=600, print_live=True, in_panel=True)
    remember_turn(f"Navegar {url}", ans)
    save_memory(f"navegar: {url}", "web", [url])


# --- LECTURA DE ARCHIVOS Y VISION ---
def resolve_pc_path(filepath_str):
    clean_str = filepath_str.strip().strip("'\"")
    p = Path(clean_str).expanduser()
    if not p.is_absolute():
        proj_candidate = TOOLS["get_project"]() / p
        if proj_candidate.exists():
            return proj_candidate
        return Path.cwd() / p
    return p


def read_any_pc_file(filepath_str):
    p = resolve_pc_path(filepath_str)
    if not p.exists():
        return None, f"No existe: {p}"
    if p.is_dir():
        items = [x.name for x in sorted(p.iterdir())[:50]]
        return None, f"'{p}' es un directorio: {', '.join(items)}"

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(p))
            paginas = [f"--- Pagina {i} ---\n{(pg.extract_text() or '').strip()}" for i, pg in enumerate(reader.pages[:30], 1) if (pg.extract_text() or "").strip()]
            return p, ("\n\n".join(paginas) if paginas else "PDF sin texto seleccionable.")
        except Exception as e:
            return None, f"Error PDF: {e}"

    if suffix == ".docx":
        try:
            import docx
            doc = docx.Document(str(p))
            parrafos = [para.text for para in doc.paragraphs if para.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_txt = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_txt:
                        parrafos.append(row_txt)
            return p, ("\n".join(parrafos) if parrafos else "Documento Word vacio.")
        except Exception as e:
            return None, f"Error Word: {e}"

    try:
        if p.stat().st_size > 800_000:
            return None, f"Archivo mayor a 800KB: {p}"
        return p, p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return None, f"Error leyendo '{p}': {e}"


def analyze_image(filepath_str, custom_question=""):
    p = resolve_pc_path(filepath_str)
    if not p.exists() or not p.is_file():
        print(f"{C_ERR}Error:{RESET} No se encontro la imagen: {p}")
        return

    panel_start("PROCESAMIENTO VISUAL [moondream + jaro-chat]", p.name)
    ocr_text, img_info = "", ""
    try:
        from PIL import Image
        import pytesseract
        with Image.open(p) as img:
            img_info = f"{img.format} | {img.size[0]}x{img.size[1]} | {img.mode}"
            ocr_text = pytesseract.image_to_string(img, lang="spa+eng").strip()
    except Exception:
        pass

    if img_info:
        print(f"{C_FRAME}│{RESET} {C_MUTED}Metadatos:{RESET} {C_TEXT}{img_info}{RESET}")
    if ocr_text:
        print(f"{C_FRAME}│{RESET} {C_MUTED}Texto OCR:{RESET} {C_TEXT}{ocr_text[:180].replace(chr(10), ' ')}{RESET}")

    vision_desc = ""
    try:
        switch_model_safely(VISION_MODEL)
        img_b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
        resp = requests.post(
            API_GENERATE,
            json={
                "model": VISION_MODEL,
                "prompt": "Describe this image in detail, including objects, text, interface elements, or diagrams.",
                "images": [img_b64],
                "stream": False,
                "keep_alive": 0,
                "options": {"temperature": 0.2, "num_ctx": 1024}
            },
            timeout=180
        )
        if resp.status_code == 200:
            vision_desc = resp.json().get("response", "").strip()
    except Exception:
        pass

    pregunta = custom_question if custom_question else "Explica detalladamente que muestra esta imagen y su contenido."
    prompt_final = f"""Datos extraidos de '{p.name}':
- Metadatos: {img_info}
- Descripcion visual: {vision_desc if vision_desc else 'No disponible'}
- Texto OCR: {ocr_text if ocr_text else 'Ninguno'}

Responde en espanol de forma directa a: {pregunta}"""

    ans = call_ollama_stream(prompt_final, role="chat", max_tokens=600, print_live=True, in_panel=True)
    remember_turn(f"Imagen {p.name}", ans)
    save_memory(f"imagen: {p.name}", "vision", [str(p)])


def analyze_file(filename):
    p = resolve_pc_path(filename)
    if p.suffix.lower() in IMAGE_EXTS:
        analyze_image(filename)
        return

    path_obj, content = read_any_pc_file(filename)
    if path_obj is None:
        print(f"{C_ERR}Error:{RESET} {content}")
        return

    panel_start("AUDITORIA TECNICA [jaro-code]", path_obj.name)
    prompt = f"""Analiza tecnicamente '{path_obj.name}'. Explica su funcionamiento, estructura y mejoras de forma directa:
{content[:2000]}"""
    ans = call_ollama_stream(prompt, role="code", max_tokens=650, print_live=True, in_panel=True)
    remember_turn(f"Analizar {path_obj.name}", ans)
    save_memory(f"analizar: {path_obj.name}", "analyze", [str(path_obj)])


# --- GENERACION DE SOFTWARE (MOTOR: jaro-code) ---
def clean_code(raw_text, filename=""):
    text = raw_text.strip()
    match = re.search(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    elif text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if filename.endswith(".css"):
        text = re.sub(r"(?m)^-\s*\{", "* {", text)
    if filename.endswith(".html"):
        text = re.sub(r'\s+onclick=["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    if filename.endswith((".css", ".js")):
        open_b = text.count("{")
        close_b = text.count("}")
        if open_b > close_b and (open_b - close_b) <= 2:
            text = text + ("\n}" * (open_b - close_b))
    return text


def ensure_interactive_html(html_code):
    injected = []
    if 'id="btn-accion"' not in html_code and "id='btn-accion'" not in html_code:
        injected.append('        <button id="btn-accion" class="btn">Explorar</button>')
    if 'id="mensaje-estado"' not in html_code and "id='mensaje-estado'" not in html_code:
        injected.append('        <p id="mensaje-estado" class="estado"></p>')

    if injected:
        block = "\n    <section class=\"card interactivo\">\n" + "\n".join(injected) + "\n    </section>\n"
        if "</main>" in html_code:
            html_code = html_code.replace("</main>", block + "</main>", 1)
        elif "</body>" in html_code:
            html_code = html_code.replace("</body>", block + "</body>", 1)
        else:
            html_code += block
    return html_code


def extract_html_selectors(html_code):
    ids = sorted(set(re.findall(r'id=["\']([^"\']+)["\']', html_code)))
    classes = sorted(set(re.findall(r'class=["\']([^"\']+)["\']', html_code)))
    return ids, classes


def smart_merge_python(old_code, new_code):
    try:
        old_tree = ast.parse(old_code)
        new_tree = ast.parse(new_code)
    except SyntaxError:
        return new_code

    old_funcs = {n.name: ast.get_source_segment(old_code, n) for n in old_tree.body if isinstance(n, ast.FunctionDef)}
    new_funcs = {n.name: ast.get_source_segment(new_code, n) for n in new_tree.body if isinstance(n, ast.FunctionDef)}
    missing = [name for name in old_funcs if name not in new_funcs]
    if not missing:
        return new_code

    print(f"{C_FRAME}│{RESET} {C_MUTED}Proteccion AST: preservando {missing}{RESET}")
    merged = []
    imports = [ast.get_source_segment(old_code, n) for n in old_tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if imports:
        merged.append("\n".join(imports))

    for fname in list(old_funcs.keys()) + [k for k in new_funcs if k not in old_funcs]:
        if fname != "main":
            src = new_funcs.get(fname) or old_funcs.get(fname)
            if src:
                merged.append(src)

    if "main" in new_funcs or "main" in old_funcs:
        merged.append(new_funcs.get("main") or old_funcs.get("main"))

    if 'if __name__' in old_code and 'if __name__' not in "\n".join(merged):
        merged.append('if __name__ == "__main__":\n    main()')

    return "\n\n\n".join(merged) + "\n"


def generate_code(task, filename, description, extra_context=""):
    prompt = f"""Genera el codigo fuente completo y funcional para: {filename}
Requerimiento: {task}
Especificacion: {description}
{extra_context}

REGLAS:
1. Devuelve UNICAMENTE el codigo fuente de {filename}, sin explicaciones ni texto adicional.
2. NO uses bloques Markdown (nada de ```).
3. Usa datos reales en espanol.
"""
    raw = call_ollama_stream(prompt, role="code", max_tokens=1100, temperature=0.15, print_live=False)
    code = clean_code(raw, filename)
    if not code:
        raise ValueError(f"Salida vacia para {filename}")
    return code


def create_website(task, research_context="", include_images=False):
    panel_start("GENERADOR WEB [jaro-code]", str(TOOLS["get_project"]()))
    print(f"{C_FRAME}│{RESET} {C_MUTED}Cambiando a nucleo de ingenieria (jaro-code)...{RESET}")

    img_instruction = ""
    if include_images or any(w in task.lower() for w in ("imagen", "imagenes", "imágenes", "fotos", "galeria")):
        img_instruction = (
            " Incluye etiquetas <figure class='media-card'><img src='https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/480px-No_image_available.svg.png' "
            "alt='Ilustracion tematica' loading='lazy'><figcaption>Descripcion visual</figcaption></figure> y estilos responsivos para imagenes."
        )

    extra_info = f"\nInformacion investigada para incluir en el contenido:\n{research_context[:1200]}\n" if research_context else ""

    html_desc = (
        "Estructura HTML5 semantica en espanol. Incluye <header>, <main class='container'>, "
        "tarjetas class='card', un boton <button id='btn-accion' class='btn'> y <p id='mensaje-estado'></p>, y <footer>."
        + img_instruction +
        " Enlaza <link rel='stylesheet' href='style.css'> y <script src='script.js'></script>."
    )
    html_code = ensure_interactive_html(generate_code(task, "index.html", html_desc, extra_info))
    print(f"{C_FRAME}│{RESET} {C_OK}✓{RESET} {TOOLS['write_file']('index.html', html_code)}")

    ids, classes = extract_html_selectors(html_code)
    ctx = f"Codigo real de index.html:\n{html_code}\nIDs: {ids} | Clases: {classes}\n"

    css_desc = (
        "CSS3 moderno tema oscuro (#0b1120), tarjetas (#111827), texto claro (#f8fafc), imagenes responsivas (max-width: 100%; border-radius: 8px;) y acento cyan (#06b6d4). "
        f"Estiliza las clases {classes} y IDs #{ids}. Cierra todas las llaves."
    )
    css_code = generate_code(task, "style.css", css_desc, ctx)
    print(f"{C_FRAME}│{RESET} {C_OK}✓{RESET} {TOOLS['write_file']('style.css', css_code)}")

    js_desc = "JavaScript con DOMContentLoaded que conecta 'btn-accion' y 'mensaje-estado'."
    js_code = generate_code(task, "script.js", js_desc, ctx)
    print(f"{C_FRAME}│{RESET} {C_OK}✓{RESET} {TOOLS['write_file']('script.js', js_code)}")

    web_check = TOOLS["run_check"]("web")
    if "exit:0" not in web_check and "Codigo de salida: 0" not in web_check:
        safe_js = (
            "document.addEventListener('DOMContentLoaded', function() {\n"
            "    const btn = document.getElementById('btn-accion');\n"
            "    const estado = document.getElementById('mensaje-estado');\n"
            "    if (btn && estado) {\n"
            "        btn.addEventListener('click', function() {\n"
            "            estado.textContent = 'JARO 1.0: Interfaz verificada y activa.';\n"
            "        });\n"
            "    }\n"
            "});\n"
        )
        TOOLS["write_file"]("script.js", safe_js)

    panel_end("Proyecto web generado | Ejecuta 'ver' para renderizar")
    save_memory(task, "web_gen", ["index.html", "style.css", "script.js"])


def create_python_script(task):
    filename = "main.py"
    match = re.search(r"([\w\-]+\.py)", task)
    if match:
        filename = match.group(1)

    panel_start("GENERADOR PYTHON [jaro-code]", filename)
    desc = "Script Python 3 modular, limpio, en espanol y con bloque if __name__ == '__main__':"
    code = generate_code(task, filename, desc)
    print(f"{C_FRAME}│{RESET} {C_OK}✓{RESET} {TOOLS['write_file'](filename, code)}")

    check_res = TOOLS["run_check"]("compile", filename)
    if "exit:0" not in check_res and "Codigo de salida: 0" not in check_res:
        fix_ctx = f"Codigo:\n{code}\nError:\n{check_res}"
        fixed = generate_code(task, filename, "Corrige los errores de sintaxis.", fix_ctx)
        TOOLS["write_file"](filename, fixed)

    run_out = TOOLS["run_check"]("run_py", filename)
    print(f"{C_FRAME}│{RESET} {C_MUTED}{run_out}{RESET}")
    panel_end("Script compilado y verificado")
    save_memory(task, "py_gen", [filename])


def edit_existing_file(task, filename):
    path_obj, current_content = read_any_pc_file(filename)
    if path_obj is None:
        print(f"{C_ERR}Error:{RESET} {current_content}")
        return

    panel_start("EDICION DE CODIGO [jaro-code]", path_obj.name)
    extra = f"Contenido actual:\n{current_content}\n"
    new_code = generate_code(task, path_obj.name, "Aplica exactamente las mejoras solicitadas.", extra)
    if path_obj.suffix == ".py":
        new_code = smart_merge_python(current_content, new_code)

    path_obj.write_text(new_code, encoding="utf-8")
    print(f"{C_FRAME}│{RESET} {C_OK}✓{RESET} Guardado en {path_obj}")
    panel_end("Modificacion aplicada")
    save_memory(task, "edit", [str(path_obj)])


def open_in_browser():
    index_path = TOOLS["get_project"]() / "index.html"
    if not index_path.is_file():
        print(f"{C_ERR}Error:{RESET} No existe index.html en {TOOLS['get_project']()}")
        return

    lp_bin = get_lightpanda_bin()
    if lp_bin:
        panel_start("LIGHTPANDA RENDER", index_path.name)
        prev_cwd = os.getcwd()
        os.chdir(TOOLS["get_project"]())
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

        httpd = TCPServer(("127.0.0.1", port), QuietHandler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            ok, rendered = lightpanda_fetch_url(f"[http://127.0.0.1](http://127.0.0.1):{port}/index.html", max_chars=2200)
            if ok:
                for line in rendered.splitlines():
                    print(f"{C_FRAME}│{RESET} {C_TEXT}{line}{RESET}")
                panel_end("Renderizado completado")
            else:
                panel_end("Abriendo navegador externo")
                webbrowser.open(index_path.as_uri())
        finally:
            httpd.shutdown()
            os.chdir(prev_cwd)
    else:
        webbrowser.open(index_path.as_uri())


def get_history_file():
    return TOOLS["get_project"]() / ".jaro_history.json"


def save_memory(task, action_type, files_touched):
    hfile = get_history_file()
    history = []
    if hfile.is_file():
        try:
            history = json.loads(hfile.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.append({
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "proyecto": TOOLS["get_project"]().name,
        "tarea": task,
        "tipo": action_type,
        "archivos": files_touched
    })
    hfile.write_text(json.dumps(history[-25:], indent=2, ensure_ascii=False), encoding="utf-8")


def show_memory():
    hfile = get_history_file()
    panel_start("REGISTRO DE OPERACIONES", TOOLS["get_project"]().name)
    if not hfile.is_file():
        print(f"{C_FRAME}│{RESET} {C_MUTED}Sin operaciones registradas en este proyecto.{RESET}")
        panel_end("0 registros")
        return
    history = json.loads(hfile.read_text(encoding="utf-8"))
    for idx, item in enumerate(history[-10:], 1):
        print(f"{C_FRAME}│{RESET} {C_PRIMARY}{idx:02d}.{RESET} {C_MUTED}[{item['fecha']}]{RESET} {C_TEXT}{item['tarea']}{RESET}")
    panel_end(f"{len(history)} registros almacenados")


def run_all_checks():
    panel_start("AUDITORIA INTEGRAL", TOOLS["get_project"]().name)
    print(f"{C_FRAME}│{RESET} {C_TEXT}{TOOLS['run_check']('web')}{RESET}")
    for item in sorted(TOOLS["get_project"]().glob("*.py")):
        print(f"{C_FRAME}│{RESET} {C_TEXT}{TOOLS['run_check']('compile', item.name)}{RESET}")
        print(f"{C_FRAME}│{RESET} {C_TEXT}{TOOLS['run_check']('run_py', item.name)}{RESET}")
    panel_end("Auditoria finalizada")


def route_task(task):
    task = task.lstrip("* ").strip()
    low = task.lower()

    if low in ("/help", "ayuda", "help", "?", "comandos"):
        mostrar_ayuda()
        return

    if low in ("/clear", "limpiar", "clear", "reset"):
        CHAT_MEMORY.clear()
        print(f"  {C_OK}✓{RESET} {C_MUTED}Memoria conversacional reiniciada.{RESET}")
        return

    if low.startswith(("/web ", "navegar ", "lightpanda ", "abrir url ", "url ")):
        for prefix in ("/web ", "lightpanda ", "abrir url ", "navegar ", "url "):
            if low.startswith(prefix):
                rest = task[len(prefix):].strip()
                parts = rest.split(maxsplit=1)
                browse_url_with_jaro(parts[0], parts[1] if len(parts) > 1 else "")
                return

    if low.startswith(("/search ", "web ", "investiga ", "investigar ", "internet ", "busca en internet ", "quien fue ", "que es ")):
        for prefix in ("/search ", "busca en internet ", "investigar ", "investiga ", "internet ", "web "):
            if low.startswith(prefix):
                query = task[len(prefix):].strip()
                if query:
                    investigate_web(query)
                    return
        if any(w in low for w in ("crea una web", "haz una web", "genera una web", "pagina web")):
            investigate_web(task)
            return

    if low.startswith(("/vision ", "/img ", "imagen ", "ver imagen ", "mira ", "procesar imagen ")):
        for prefix in ("/vision ", "/img ", "procesar imagen ", "ver imagen ", "imagen ", "mira "):
            if low.startswith(prefix):
                rest = task[len(prefix):].strip()
                parts = rest.split(maxsplit=1)
                analyze_image(parts[0], parts[1] if len(parts) > 1 else "")
                return

    if low.startswith(("/read ", "leer ", "mostrar ", "cat ")):
        parts = task.split(maxsplit=1)
        if len(parts) == 2:
            target = parts[1].strip()
            if resolve_pc_path(target).suffix.lower() in IMAGE_EXTS:
                analyze_image(target)
                return
            path_obj, content = read_any_pc_file(target)
            if path_obj is None:
                print(f"{C_ERR}Error:{RESET} {content}")
            else:
                panel_start("LECTOR DE ARCHIVOS", str(path_obj))
                for line in content[:3500].splitlines():
                    print(f"{C_FRAME}│{RESET} {C_TEXT}{line}{RESET}")
                panel_end(f"{min(len(content), 3500)} / {len(content)} caracteres")
            return

    if low.startswith(("analizar ", "explicar ", "resumir ", "resume ")):
        fname = task.split(maxsplit=1)[1].strip()
        if fname.startswith(("http://", "https://")):
            browse_url_with_jaro(fname, task)
            return
        analyze_file(fname)
        return

    if low.startswith("proyecto"):
        parts = task.split(maxsplit=1)
        print(f"  {C_OK}✓{RESET} {C_TEXT}{TOOLS['set_project'](parts[1] if len(parts) == 2 else '')}{RESET}")
        return

    if low in ("/preview", "ver", "abrir", "navegador", "preview"):
        open_in_browser()
        return

    if low in ("/tree", "archivos", "listar", "ls", "ver archivos"):
        panel_start("ARBOL DE PROYECTO", TOOLS["get_project"]().name)
        print(TOOLS["list_files"]("."))
        panel_end("Listado completado")
        return

    if low in ("/history", "memoria", "historial"):
        show_memory()
        return

    if low in ("/check", "verificar", "check", "pruebas"):
        run_all_checks()
        return

    if low.startswith("buscar "):
        query = task.split(maxsplit=1)[1].strip()
        panel_start("BUSQUEDA EN CODIGO", query)
        print(TOOLS["search_code"](query))
        panel_end("Busqueda finalizada")
        return

    url_in_prompt = re.search(r"(https?://[^\s\)\]]+)", task)
    if url_in_prompt:
        browse_url_with_jaro(url_in_prompt.group(1), task)
        return

    file_match = re.search(r"([\w\-\./~]+\.(?:html|css|js|py|txt|json|md|sh|conf))", task)
    if file_match and any(w in low for w in ("edita", "modifica", "cambia", "agrega", "añade", "corrige", "arregla")):
        edit_existing_file(task, file_match.group(1))
        return

    if any(w in low for w in ("crea un script", "crea una calculadora", "haz un script", "programa en python", "archivo .py")) or (
        ".py" in low and any(w in low for w in ("crea", "haz", "genera", "construye"))
    ):
        create_python_script(task)
        return

    if any(w in low for w in ("crea una web", "crea un sitio", "haz una pagina", "haz una web", "genera una web", "crea una landing")):
        create_website(task)
        return

    # Enrutamiento dinamico entre jaro-code y jaro-chat
    is_code = any(w in low for w in ("codigo", "código", "funcion", "función", "python", "javascript", "html", "css", "sql", "linux", "bash", "algoritmo", "error", "bug", "clase", "api"))
    role = "code" if is_code else "chat"
    full_prompt = build_conversational_prompt(task)
    ans = call_ollama_stream(full_prompt, role=role, max_tokens=750, print_live=True, in_panel=False)
    remember_turn(task, ans)


def main():
    prewarm_model_async()
    mostrar_banner()

    while True:
        try:
            proj_name = TOOLS["get_project"]().name
            ram_now = get_ram_telemetry().split()[0]
            prompt_str = (
                f"\n{C_PRIMARY}JARO{C_MUTED}@{C_TEXT}{proj_name}{RESET} "
                f"{C_FRAME}[{C_WARN}{ram_now}{C_FRAME}]{RESET} "
                f"{C_PRIMARY}▸{RESET} "
            )
            task = input(prompt_str).strip()

            if task.lower() in ("/exit", "salir", "exit", "quit"):
                print(f"{C_MUTED}Nucleo JARO 1.0 detenido.{RESET}")
                break

            if not task:
                continue

            route_task(task)

        except KeyboardInterrupt:
            print(f"\n{C_MUTED}Nucleo JARO 1.0 detenido.{RESET}")
            break
        except Exception as error:
            print(f"\n{C_ERR}[ERROR]{RESET} {error}")


if __name__ == "__main__":
    main()
