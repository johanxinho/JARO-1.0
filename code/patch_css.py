import re

def fix_css(filepath):
    try:
        content = filepath.read_text(encoding="utf-8")
        # Corrección definitiva: cualquier guion seguido de llave se vuelve selector universal *
        fixed = re.sub(r'-\s*\{', '* {', content)
        if fixed != content:
            filepath.write_text(fixed, encoding="utf-8")
            print(f"[REPARACIÓN CSS] Selector corregido a '* {{' en {filepath.name}")
    except Exception as e:
        print(f"Error: {e}")
