import time
import requests
from pathlib import Path

ENV_FILE = Path.home() / ".config/johanai/env"

# Modelo principal y modelo de respaldo
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
]


def get_api_key():
    if not ENV_FILE.exists():
        raise RuntimeError("No se encontró la configuración de Gemini.")

    for line in ENV_FILE.read_text().splitlines():
        if line.startswith("GEMINI_API_KEY="):
            key = line.split("=", 1)[1].strip()
            if key:
                return key

    raise RuntimeError("La clave de Gemini está vacía.")


def ask_gemini(screen_text):
    key = get_api_key()

    prompt = (
        "Eres JohanAI, un asistente inteligente. "
        "Responde en español, con precisión y brevedad. "
        "No saludes ni hagas introducciones innecesarias.\\n\\n"
        "INSTRUCCIONES:\\n"
        "- Selección múltiple: indica letra y texto de la opción. "
        "No inventes respuestas.\\n"
        "- Varias preguntas: responde cada una numerada.\\n"
        "- Evaluaciones: analiza las preguntas visibles.\\n"
        "- Matemáticas: resultado y procedimiento esencial.\\n"
        "- Código: identifica el error y su solución.\\n"
        "- Si el OCR no permite leer una pregunta u opción, indícalo.\\n"
        "- Si no hay preguntas, describe brevemente el contenido.\\n\\n"
        "TEXTO RECONOCIDO EN LA PANTALLA:\\n"
        f"{screen_text[:18000]}"
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 250
        }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key
    }

    errors = []

    for model in MODELS:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{model}:generateContent"
        )

        for attempt in range(2):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=(10, 60)
                )

                if response.status_code in (
                    429, 500, 502, 503, 504
                ):
                    errors.append(
                        f"{model}: HTTP {response.status_code}"
                    )

                    if attempt == 0:
                        time.sleep(2)
                        continue

                    break

                if not response.ok:
                    raise RuntimeError(
                        f"Gemini HTTP {response.status_code}: "
                        f"{response.text[:400]}"
                    )

                data = response.json()
                candidates = data.get("candidates", [])

                if not candidates:
                    raise RuntimeError(
                        f"{model} no devolvió ninguna respuesta."
                    )

                parts = candidates[0].get(
                    "content", {}
                ).get("parts", [])

                answer = "\\n".join(
                    part["text"]
                    for part in parts
                    if "text" in part
                ).strip()

                if answer:
                    return answer

                raise RuntimeError(
                    f"{model} devolvió una respuesta vacía."
                )

            except requests.RequestException as error:
                errors.append(f"{model}: {error}")

                if attempt == 0:
                    time.sleep(2)
                    continue

                break

    raise RuntimeError(
        "Los modelos principales están temporalmente ocupados. "
        "Inténtalo nuevamente. Detalles: " + "; ".join(errors)
    )
