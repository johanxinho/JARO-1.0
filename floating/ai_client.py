import time
import requests
from pathlib import Path

ENV_FILE = Path.home() / ".config/johanai/env"
MODEL = "gemini-3.5-flash-lite"


def get_api_key():
    if not ENV_FILE.exists():
        raise RuntimeError("No se encontró el archivo de configuración de Gemini.")

    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key

    raise RuntimeError("No se encontró GEMINI_API_KEY en la configuración.")


def ask_gemini(screen_text):
    key = get_api_key()

    prompt = (
        "Eres JohanAI, un asistente inteligente. "
        "Responde en español, directamente y con precisión. "
        "No hagas introducciones innecesarias.\n\n"
        "INSTRUCCIONES:\n"
        "- Selección múltiple: indica la letra y el texto de la opción.\n"
        "- Varias preguntas: responde cada una numerada.\n"
        "- Matemáticas: da el resultado y el procedimiento esencial.\n"
        "- Código: identifica errores y proporciona soluciones.\n"
        "- No inventes información.\n"
        "- Si el texto no se entiende, indícalo.\n"
        "- Si no hay preguntas, describe brevemente el contenido.\n\n"
        "TEXTO RECONOCIDO EN LA PANTALLA:\n"
        f"{screen_text[:18000]}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 250
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key
    }

    for attempt in range(3):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=(10, 45)
            )

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
                    continue

            response.raise_for_status()

            data = response.json()
            candidates = data.get("candidates", [])

            if not candidates:
                raise RuntimeError("Gemini no devolvió ninguna respuesta.")

            parts = candidates[0].get("content", {}).get("parts", [])
            answer = "\n".join(
                part["text"] for part in parts if "text" in part
            ).strip()

            if answer:
                return answer

            raise RuntimeError("Gemini devolvió una respuesta vacía.")

        except requests.exceptions.Timeout:
            if attempt == 2:
                raise RuntimeError("Gemini tardó demasiado en responder.")
            time.sleep(3)

        except requests.exceptions.RequestException as error:
            if attempt == 2:
                raise RuntimeError(f"Error de conexión con Gemini: {error}")
            time.sleep(3)

    raise RuntimeError("No se pudo obtener una respuesta de Gemini.")
