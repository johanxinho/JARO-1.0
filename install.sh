#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Instalador Oficial JARO 1.0 (Linux) ==="

if ! command -v ollama &> /dev/null; then
    echo "[ERROR] Ollama no esta instalado. Instalalo en https://ollama.com"
    exit 1
fi

pip3 install -r "$SCRIPT_DIR/requirements.txt" --break-system-packages 2>/dev/null || pip3 install -r "$SCRIPT_DIR/requirements.txt"

ollama pull qwen2.5-coder:1.5b
ollama pull llama3.2:1b
ollama pull moondream

ollama create jaro-code -f "$SCRIPT_DIR/Modelfile.code"
ollama create jaro-chat -f "$SCRIPT_DIR/Modelfile.chat"

mkdir -p ~/.local/bin
printf "#!/usr/bin/env bash\npython3 \"%s/code/agent.py\" \"\$@\"\n" "$SCRIPT_DIR" > ~/.local/bin/jaro
chmod +x ~/.local/bin/jaro

echo "[OK] Instalacion completada. Ejecuta jaro en tu terminal."
