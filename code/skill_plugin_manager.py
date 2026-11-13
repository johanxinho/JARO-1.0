import importlib.util, sys, json, re, gc
from pathlib import Path
from memory_db import log_skill_execution

BASE_DIR = Path.home() / "JohanAI"
PLUGINS_DIR = BASE_DIR / "plugins"
SKILLS_DIR = BASE_DIR / "skills"

def run_plugin(plugin_name, payload=None):
    plugin_path = PLUGINS_DIR / f"{plugin_name}.py"
    if not plugin_path.exists():
        return f"Error: Plugin {plugin_name} no existe."
    module = None
    try:
        spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return str(module.run(payload or {}))
    except Exception as e:
        return f"Error en plugin {plugin_name}: {e}"
    finally:
        sys.modules.pop(plugin_name, None)
        if module is not None: del module
        gc.collect()

def execute_skill(skill_name, params, tarea_origen="manual"):
    skill_file = SKILLS_DIR / f"{skill_name}.json"
    if not skill_file.exists():
        msg = f"Skill {skill_name} no encontrada."
        log_skill_execution(skill_name, tarea_origen, params, "ERROR_NOT_FOUND", msg)
        return msg
    try:
        skill_data = json.loads(skill_file.read_text(encoding="utf-8"))
        target_plugin = skill_data.get("plugin")
        output = run_plugin(target_plugin, params) if target_plugin else f"Skill {skill_name}: {skill_data.get('instructions', '')}"
        log_skill_execution(skill_name, tarea_origen, params, "SUCCESS", output)
        return output
    except Exception as e:
        err = f"Fallo en skill {skill_name}: {e}"
        log_skill_execution(skill_name, tarea_origen, params, "ERROR", err)
        return err

def intercept_and_run_midtask_skills(llm_response, user_task, call_ollama_fn):
    match = re.search(r"\[SKILL:([a-zA-Z0-9_-]+)\|(\{.*?\})\]", llm_response)
    if not match: return llm_response
    skill_name = match.group(1)
    try: params = json.loads(match.group(2))
    except Exception: params = {}
    res = execute_skill(skill_name, params, tarea_origen=user_task)
    return call_ollama_fn(f"Tarea: {user_task}\nResultado skill {skill_name}:\n{res}\nCompleta la respuesta:")
