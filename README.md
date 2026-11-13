# JARO 1.0

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Mint%20%7C%20Ubuntu%20%7C%20Debian-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![RAM](https://img.shields.io/badge/Hardware-4GB%20RAM%20Optimized-10B981?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-06B6D4?style=for-the-badge)

**JARO 1.0** es un sistema de inteligencia artificial autónomo, multimodal y 100% local desarrollado por **Johan Restrepo**. Está diseñado para ejecutar tareas de ingeniería de software, auditoría de código, análisis documental, visión artificial e investigación web en tiempo real sobre equipos con **4 GB de memoria RAM**, sin depender de APIs ni servidores en la nube.

---

## Arquitectura del Sistema

JARO 1.0 opera bajo una arquitectura modular de **enrutamiento cognitivo con intercalado de modelos** y exclusión mutua en memoria RAM:

```text
┌──────────────────────────────────────────────────────────────────────┐
│                     JARO 1.0 // KERNEL HUD (CLI)                     │
│        Telemetría RAM (/proc/meminfo) · Streaming · tok/s            │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   ORQUESTADOR Y ENRUTADOR (agent.py)                 │
│     Clasificación de intenciones · Órdenes encadenadas · Escudo ID   │
└───┬──────────────────────────────┼───────────────────────────────┬───┘
    │                              │                               │
    ▼                              ▼                               ▼
┌─────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐
│   NÚCLEO NEURONAL   │  │   SANDBOX & CÓDIGO   │  │  WEB & MULTIMODAL │
│   (Ollama Local)    │  │      (tools.py)      │  │                   │
├─────────────────────┤  ├──────────────────────┤  ├───────────────────┤
│ • jaro-code (1.5B)  │  │ • Protección AST     │  │ • Lightpanda      │
│ • jaro-chat (1.0B)  │  │ • Sincronización DOM │  │ • Tesseract OCR   │
│ • moondream (1.8B)  │  │ • Compilador Python  │  │ • PyPDF / DOCX    │
└─────────────────────┘  └──────────────────────┘  └───────────────────┘
```

### Capas y Componentes Técnicos

| Capa / Módulo | Archivo / Motor | Responsabilidad Técnica | Gestión de Memoria |
| :--- | :--- | :--- | :--- |
| **Interfaz y Enrutador** | `code/agent.py` | Interfaz HUD en consola, clasificación de intenciones, streaming token por token y filtro de identidad en vivo. | Hilo asíncrono de precarga y búfer deslizante de baja latencia. |
| **Caja de Herramientas** | `code/tools.py` | Aislamiento de proyectos en `workspace/`, escritura segura, compilación Python y validación de estructura DOM. | Ejecución determinista sin sobrecarga de modelos. |
| **Motor de Ingeniería** | `jaro-code` (`Modelfile.code`) | Generación de software (Python, HTML5, CSS3, JS) y auditoría técnica de código fuente. | Cuantizado en 4 bits (`num_ctx 2048`), se descarga con `keep_alive: 0` al cambiar de rol. |
| **Motor Conversacional** | `jaro-chat` (`Modelfile.chat`) | Síntesis de investigaciones web, redacción técnica y razonamiento general en español. | Cuantizado en 4 bits con penalización anti-bucles (`repeat_penalty 1.25`). |
| **Navegación Headless** | `Lightpanda` + `BeautifulSoup` | Renderizado del DOM con ejecución real de JavaScript y limpieza de etiquetas HTML innecesarias. | Proceso externo efímero que libera memoria al terminar la extracción. |
| **Visión y Documentos** | `moondream` + `Tesseract` + `pypdf` | Lectura de archivos `.pdf` y `.docx`, reconocimiento óptico de caracteres (OCR) y análisis visual. | Exclusión mutua estricta: descarga los motores de texto antes de cargar visión. |

---

## Catálogo Completo de Comandos

### 1. Ingeniería y Desarrollo (`jaro-code`)
| Comando | Alias | Descripción |
| :--- | :--- | :--- |
| `crea una web <descripción>` | `haz una web` | Genera `index.html`, `style.css` y `script.js` con selectores DOM sincronizados. |
| `crea un script <descripción>` | `programa en python` | Genera, compila (`py_compile`) y verifica la ejecución de un script en Python 3. |
| `edita <archivo> <instrucción>` | `modifica`, `corrige` | Edita archivos existentes protegiendo funciones previas mediante análisis **AST**. |
| `analizar <ruta_archivo>` | `explicar` | Realiza una auditoría técnica de estructura, errores y mejoras sobre un archivo. |
| `/check` | `verificar`, `pruebas` | Ejecuta pruebas de sintaxis Python y validación de estructura DOM en el proyecto. |
| `/preview` | `ver`, `abrir` | Levanta un servidor HTTP local temporal y renderiza la web con **Lightpanda**. |

### 2. Investigación y Órdenes Encadenadas (`jaro-chat` + `jaro-code`)
| Comando | Alias | Descripción |
| :--- | :--- | :--- |
| `investiga <tema>` | `/search`, `internet` | Consulta fuentes en internet, extrae el artículo principal y redacta una síntesis. |
| `investiga <tema> y crea una web` | — | Encadena ambos motores: investiga el tema con `jaro-chat` y construye la web con `jaro-code`. |
| `/web <url>` | `navegar <url>` | Renderiza cualquier URL mediante Lightpanda y resume su contenido. |

### 3. Documentos y Visión Artificial (`moondream` + `Tesseract OCR`)
| Comando | Alias | Descripción |
| :--- | :--- | :--- |
| `/read <ruta>` | `leer <ruta>` | Extrae texto de código fuente, documentos PDF (`.pdf`) o Word (`.docx`). |
| `/vision <ruta> [pregunta]` | `imagen <ruta>` | Extrae metadatos, lee texto incrustado (OCR) y describe el contenido visual de la imagen. |

### 4. Gestión de Proyectos y Control del Sistema
| Comando | Alias | Descripción |
| :--- | :--- | :--- |
| `proyecto <nombre>` | — | Crea o cambia la carpeta de trabajo activa dentro de `workspace/`. |
| `/tree` | `archivos`, `ls` | Lista los archivos y tamaños del proyecto activo. |
| `buscar <texto>` | — | Busca cadenas de texto dentro de todos los archivos del proyecto actual. |
| `/status` | `estado`, `sistema` | Muestra diagnóstico de sistema operativo, RAM física, motores y rutas. |
| `/bench` | `benchmark` | Ejecuta una prueba de rendimiento midiendo latencia y `tokens/segundo`. |
| `/history` | `memoria`, `historial` | Muestra el registro persistente de operaciones realizadas en el proyecto. |
| `/clear` | `limpiar`, `reset` | Reinicia la memoria conversacional de corto plazo. |
| `/help` | `ayuda`, `?` | Despliega el manual de operaciones dentro de la terminal HUD. |
| `/exit` | `salir`, `quit` | Detiene el núcleo de JARO 1.0 y cierra la sesión. |

---

## Instalación Multiplataforma

### Requisitos Previos
1. **Python 3.9** o superior.
2. **Ollama** instalado y ejecutándose ([ollama.com](https://ollama.com)).
3. *(Opcional)* **Lightpanda** para renderizado web con JavaScript y **Tesseract OCR** (`tesseract-ocr-spa`) para lectura de texto en imágenes.

### Linux (Ubuntu / Linux Mint / Debian)
```bash
git clone https://github.com/johanxinho/JARO-1.0.git
cd JARO-1.0
chmod +x install.sh
./install.sh
```
Inicia el sistema desde cualquier directorio ejecutando:
```bash
jaro
```

### Windows 10 / 11
1. Clona el repositorio o descárgalo desde **Code -> Download ZIP** y descomprímelo.
2. Haz doble clic en **`install.bat`** para instalar dependencias y compilar los motores.
3. Ejecuta **`jaro.bat`** para iniciar la terminal HUD.

---

## Licencia

Distribuido bajo la **Licencia MIT**. Consulta el archivo [`LICENSE`](LICENSE) para más detalles.  
Desarrollado por **Johan Restrepo**.
