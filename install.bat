@echo off
title Instalador Oficial JARO 1.0 (Windows)
set "BASE_DIR=%~dp0"
echo === Instalador Oficial JARO 1.0 (Windows) ===

where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Ollama no esta instalado. Descargalo en https://ollama.com
    pause
    exit /b 1
)

pip install -r "%BASE_DIR%requirements.txt"
ollama pull qwen2.5-coder:1.5b
ollama pull llama3.2:1b
ollama pull moondream

ollama create jaro-code -f "%BASE_DIR%Modelfile.code"
ollama create jaro-chat -f "%BASE_DIR%Modelfile.chat"

echo @echo off > "%BASE_DIR%jaro.bat"
echo python "%BASE_DIR%code\agent.py" %%* >> "%BASE_DIR%jaro.bat"

echo [OK] Instalacion completada. Ejecuta jaro.bat para iniciar.
pause
