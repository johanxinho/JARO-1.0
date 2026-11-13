# JARO 1.0

Entorno local de inteligencia artificial autonomo y multimodal desarrollado por **Johan Restrepo**, optimizado para equipos con **4 GB de RAM**.

## Caracteristicas
- **Arquitectura Dual Intercalada:** Alterna entre `jaro-code` (ingenieria de software) y `jaro-chat` (investigacion y analisis) con gestion dinamica de memoria (`keep_alive: 0`).
- **Proteccion AST y DOM:** Preserva funciones Python existentes mediante analisis sintactico AST y sincroniza selectores HTML/CSS/JS.
- **Navegador Headless:** Integracion con **Lightpanda** para renderizado web con JavaScript.
- **Documentos y Vision:** Lectura de `.pdf` y `.docx`, OCR local con Tesseract y analisis visual con `moondream`.

## Instalacion

### Linux
```bash
git clone https://github.com/johanxinho/JARO-1.0.git
cd JARO-1.0
./install.sh
```

### Windows 10 / 11
1. Descarga o clona el repositorio.
2. Ejecuta `install.bat`.
3. Inicia con `jaro.bat`.

## Licencia
MIT License - Johan Restrepo.
