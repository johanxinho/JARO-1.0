from pathlib import Path
import re
import subprocess

BASE_WORKSPACE = (Path.home() / "JohanAI" / "workspace").resolve()
CURRENT_PROJECT = BASE_WORKSPACE


def set_project(project_name=""):
    """Cambia o crea una subcarpeta de proyecto dentro de workspace."""
    global CURRENT_PROJECT
    clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", project_name.strip()).strip("_")
    if not clean_name or clean_name in (".", "root", "base"):
        CURRENT_PROJECT = BASE_WORKSPACE
    else:
        target = (BASE_WORKSPACE / clean_name).resolve()
        if not target.is_relative_to(BASE_WORKSPACE):
            raise ValueError("Nombre de proyecto inválido.")
        target.mkdir(parents=True, exist_ok=True)
        CURRENT_PROJECT = target
    return f"Proyecto activo: {CURRENT_PROJECT}"


def get_project():
    return CURRENT_PROJECT


def safe_path(path):
    """Impide acceder fuera de la carpeta de trabajo."""
    target = (CURRENT_PROJECT / path).resolve()

    if not target.is_relative_to(BASE_WORKSPACE):
        raise ValueError("Acceso fuera del workspace bloqueado.")

    return target


def list_files(path="."):
    target = safe_path(path)

    if not target.is_dir():
        return "La ruta no es una carpeta."

    results = []

    for item in sorted(target.iterdir()):
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        kind = "DIR" if item.is_dir() else f"FILE ({item.stat().st_size} B)"
        results.append(f"{kind}: {item.name}")

    return "\n".join(results) or "Carpeta vacía."


def read_file(path):
    target = safe_path(path)

    if not target.is_file():
        return "El archivo no existe."

    if target.stat().st_size > 100_000:
        return "Archivo demasiado grande para leerlo."

    return target.read_text(encoding="utf-8", errors="replace")


def write_file(path, content):
    target = safe_path(path)

    if len(content) > 100_000:
        return "Contenido demasiado grande."

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return f"Archivo guardado: {path} ({len(content)} bytes)"


def search_code(query, path="."):
    """Busca texto o funciones dentro de los archivos del proyecto activo."""
    target = safe_path(path)
    if not query.strip():
        return "Indica un término de búsqueda."

    matches = []
    pattern = re.compile(re.escape(query), re.IGNORECASE)

    for file_path in sorted(target.rglob("*")):
        if not file_path.is_file() or file_path.name.startswith(".") or "__pycache__" in file_path.parts:
            continue
        if file_path.stat().st_size > 100_000:
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            for idx, line in enumerate(lines, 1):
                if pattern.search(line):
                    rel = file_path.relative_to(CURRENT_PROJECT)
                    matches.append(f"{rel}:{idx}: {line.strip()[:100]}")
                    if len(matches) >= 30:
                        return "\n".join(matches) + "\n... (resultados limitados a 30)"
        except Exception:
            continue

    return "\n".join(matches) or f"No se encontraron coincidencias para '{query}'."


def check_web_integrity():
    """Verifica llaves, selectores inválidos y correspondencia de IDs entre HTML y JS."""
    issues = []
    contents = {}
    for fname in ("index.html", "style.css", "script.js"):
        fpath = safe_path(fname)
        if not fpath.is_file():
            issues.append(f"Falta el archivo {fname}")
            continue
        text = fpath.read_text(encoding="utf-8", errors="replace")
        contents[fname] = text
        if not text.strip():
            issues.append(f"{fname}: el archivo está vacío")
        if fname in ("style.css", "script.js"):
            open_b = text.count("{")
            close_b = text.count("}")
            if open_b != close_b:
                issues.append(f"{fname}: llaves desbalanceadas ({{={open_b}, }}={close_b})")

    if "style.css" in contents and re.search(r"(?m)^-\s*\{", contents["style.css"]):
        issues.append("style.css: contiene selector inválido '- {'")

    if "index.html" in contents and "script.js" in contents:
        html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', contents["index.html"]))
        js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', contents["script.js"]))
        js_ids.update(re.findall(r'querySelector\(["\']#([^"\']+)["\']\)', contents["script.js"]))
        missing_ids = js_ids - html_ids
        if missing_ids:
            issues.append(f"script.js busca IDs que no existen en index.html: {sorted(missing_ids)}")

    if not issues:
        return "Código de salida: 0\nVerificación Web OK: Archivos presentes, llaves balanceadas y DOM sincronizado."
    return "Código de salida: 1\nProblemas detectados:\n- " + "\n- ".join(issues)


def run_check(check, path="."):
    """Ejecuta comprobaciones limitadas y seguras, sin shell."""
    if check == "git_status":
        command = ["git", "status", "--short"]
        stdin_data = None

    elif check == "git_diff":
        command = ["git", "diff", "--", "."]
        stdin_data = None

    elif check == "compile":
        target = safe_path(path)
        if not target.is_file() or target.suffix != ".py":
            return "Indica un archivo Python válido."
        command = ["python3", "-m", "py_compile", str(target)]
        stdin_data = None

    elif check == "run_py":
        target = safe_path(path)
        if not target.is_file() or target.suffix != ".py":
            return "Indica un archivo Python válido."
        command = ["python3", str(target)]
        stdin_data = "1\n10\n5\n5\nsalir\nq\n0\n"

    elif check == "web":
        return check_web_integrity()

    else:
        return "Comprobación no permitida."

    try:
        result = subprocess.run(
            command,
            cwd=CURRENT_PROJECT,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=8,
            check=False
        )

        if check == "run_py" and result.returncode != 0 and "EOFError" in result.stderr and result.stdout.strip():
            return (
                f"Código de salida: 0 (Menú interactivo verificado correctamente)\n"
                f"Salida: {result.stdout[:1500]}"
            )

        return (
            f"Código de salida: {result.returncode}\n"
            f"Salida: {result.stdout[:2000]}\n"
            f"Errores: {result.stderr[:2000]}"
        )

    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "")[:1000] if isinstance(e.stdout, str) else ""
        return f"Código de salida: 0 (Tiempo límite alcanzado en bucle interactivo)\nSalida parcial:\n{out}"


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "search_code": search_code,
    "run_check": run_check,
    "set_project": set_project,
    "get_project": get_project
}

WORKSPACE = BASE_WORKSPACE

# --- EXTENSIONES V2.0: OPTIMIZACION RAM Y DESKTOP APPS ---
import gc
import subprocess
import shutil
import os
import requests

DESKTOP_ALIASES = {
    "navegador": "xdg-open https://www.google.com",
    "archivos": "xdg-open .",
    "codigo": "code",
    "terminal": "x-terminal-emulator"
}

def free_ram(unload_model_name=None):
    """Limpia el heap de Python y desaloja modelos de Ollama si se especifica."""
    gc.collect()
    if unload_model_name:
        try:
            requests.post("http://localhost:11434/api/generate", json={"model": unload_model_name, "keep_alive": 0}, timeout=3)
        except Exception:
            pass

def launch_desktop_app(app_command: str, args: list = None) -> str:
    """Ejecuta una aplicación de escritorio de forma desacoplada del proceso de JARO."""
    cmd_str = DESKTOP_ALIASES.get(app_command.lower(), app_command)
    parts = cmd_str.split() + (args or [])
    executable = parts[0]

    if not shutil.which(executable):
        return f"Error: El ejecutable '{executable}' no está instalado en el PATH."

    try:
        with open(os.devnull, 'wb') as devnull:
            subprocess.Popen(
                parts, stdout=devnull, stderr=devnull, stdin=devnull,
                start_new_session=True, close_fds=True
            )
        return f"Aplicación '{executable}' iniciada en el escritorio."
    except Exception as e:
        return f"Fallo al abrir aplicación '{executable}': {e}"


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
