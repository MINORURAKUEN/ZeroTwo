# 📁 Estructura Modular del Proyecto

## 🎯 Objetivo

Separar el bot monolítico en módulos organizados para facilitar el mantenimiento y colaboración.

## 📦 Estructura de Archivos

```
Rikka-Bot/
│
├── 📄 main.py                      # Punto de entrada principal
├── 📄 requirements.txt             # Dependencias Python
├── 📄 README.md                    # Documentación principal
├── 📄 LICENSE                      # Licencia MIT
├── 📄 .gitignore                   # Archivos ignorados por Git
├── 📄 install_termux.sh            # Script de instalación Termux
│
├── 📁 handlers/                    # Manejadores de comandos
│   ├── 📄 __init__.py
│   ├── 📄 start_handler.py
│   ├── 📄 help_handler.py
│   ├── 📄 compress_handler.py
│   ├── 📄 thumbnail_handler.py
│   ├── 📄 subtitles_handler.py
│   ├── 📄 extract_audio_handler.py
│   ├── 📄 download_handler.py
│   ├── 📄 anime_handler.py
│   ├── 📄 video_handler.py
│   ├── 📄 photo_handler.py
│   ├── 📄 document_handler.py
│   ├── 📄 url_handler.py
│   └── 📄 button_callback_handler.py
│
├── 📁 utils/                       # Utilidades
│   ├── 📄 __init__.py
│   └── 📄 video_processor.py      # ✅ Clase VideoProcessor
│
└── 📁 downloaders/                 # Descargadores
    ├── 📄 __init__.py
    ├── 📄 mega_downloader.py       # ✅ Clase MEGADownloader
    └── 📄 mediafire_downloader.py  # ✅ Clase MediaFireDownloader
```

## ✅ Módulos Completados

### 1. `utils/video_processor.py`
```python
from utils import VideoProcessor

# Métodos:
VideoProcessor.compress_video_resolution(...)
VideoProcessor.add_thumbnail_fast(...)
VideoProcessor.burn_subtitles(...)
VideoProcessor.extract_audio(...)
```

### 2. `downloaders/mega_downloader.py`
```python
from downloaders import MEGADownloader

success, file_path, error = await MEGADownloader.download(url, output_dir)
```

### 3. `downloaders/mediafire_downloader.py`
```python
from downloaders import MediaFireDownloader

success, file_path, error = await MediaFireDownloader.download(url, output_dir)
```

## ⚙️ Cómo Funciona

### 1. Inicialización (`main.py`)
```python
# Crear cliente de Pyrogram
app = Client("video_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Estado global
user_states = {}

# Registrar handlers
from handlers import start_handler
start_handler.register(app)
```

### 2. Estructura de Handler

Cada handler debe tener una función `register(app, ...)`:

```python
# handlers/start_handler.py
from pyrogram import filters
from pyrogram.types import Message

def register(app):
    @app.on_message(filters.command("start"))
    async def start_command(client, message: Message):
        await message.reply_text("¡Hola!")
```

### 3. Uso de Utilidades

```python
# handlers/compress_handler.py
from utils import VideoProcessor

def register(app, user_states, work_dir):
    @app.on_message(filters.command("compress"))
    async def compress_command(client, message: Message):
        # Usar VideoProcessor
        success = VideoProcessor.compress_video_resolution(
            input_path, output_path, scale='1280:720'
        )
```

## 🔨 Tareas Pendientes

### Prioridad Alta
- [ ] Separar `start_handler.py`
- [ ] Separar `help_handler.py`
- [ ] Separar `compress_handler.py`
- [ ] Separar `video_handler.py`
- [ ] Separar `button_callback_handler.py`

### Prioridad Media
- [ ] Separar `thumbnail_handler.py`
- [ ] Separar `subtitles_handler.py`
- [ ] Separar `extract_audio_handler.py`
- [ ] Separar `download_handler.py`
- [ ] Separar `anime_handler.py`

### Prioridad Baja
- [ ] Separar `photo_handler.py`
- [ ] Separar `document_handler.py`
- [ ] Separar `url_handler.py`

## 📝 Guía de Migración

### Paso 1: Identificar el Handler

Buscar en `telegram_video_bot_pyrogram.py`:
```python
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    # ... código ...
```

### Paso 2: Crear Archivo del Handler

Crear `handlers/start_handler.py`:
```python
from pyrogram import filters, enums
from pyrogram.types import Message

def register(app):
    @app.on_message(filters.command("start"))
    async def start_command(client, message: Message):
        # ... código copiado ...
```

### Paso 3: Importar en main.py

```python
from handlers import start_handler
start_handler.register(app)
```

### Paso 4: Probar

```bash
python main.py
```

## 🎨 Beneficios de la Modularización

✅ **Mantenimiento más fácil** - Cada archivo tiene una responsabilidad clara
✅ **Colaboración mejorada** - Múltiples personas pueden trabajar en paralelo
✅ **Testing más simple** - Probar módulos individuales
✅ **Código más limpio** - Menos líneas por archivo
✅ **Escalabilidad** - Agregar nuevas funciones fácilmente

## 📊 Métricas

| Archivo | Líneas | Estado |
|---------|--------|--------|
| `telegram_video_bot_pyrogram.py` | ~1800 | Monolítico |
| `main.py` | ~100 | ✅ Completado |
| `utils/video_processor.py` | ~300 | ✅ Completado |
| `downloaders/mega_downloader.py` | ~80 | ✅ Completado |
| `downloaders/mediafire_downloader.py` | ~150 | ✅ Completado |
| Handlers (13 archivos) | ~1200 | ⏳ Pendiente |

## 🚀 Próximos Pasos

1. Migrar handlers uno por uno
2. Probar cada handler individualmente
3. Actualizar documentación
4. Crear tests unitarios
5. Publicar en GitHub

---

**Estado Actual**: 40% completado
**Última actualización**: 2026-03-21
