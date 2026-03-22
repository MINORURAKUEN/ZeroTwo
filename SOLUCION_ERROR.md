# 🔧 SOLUCIÓN RÁPIDA - Error de Handlers

## ❌ Error Actual:
```
TypeError: register() missing 1 required positional argument: 'user_states'
```

## ✅ Solución:

### Opción 1: Descargar archivos actualizados

Los archivos en el `.tar.gz` están actualizados. Extráelos de nuevo:

```bash
cd ~
rm -rf ZeroTwo  # Eliminar versión antigua
tar -xzf rikka-bot-modules.tar.gz
mv rikka-bot-modules ZeroTwo
cd ZeroTwo
python main.py
```

---

### Opción 2: Corregir manualmente

Si prefieres corregir el archivo actual:

```bash
cd ~/ZeroTwo
nano main.py
```

Busca la línea (alrededor de línea 55) donde dice:
```python
# Estado de usuarios
user_states = {}

# Importar handlers
from handlers import (
```

Y verifica que `user_states = {}` esté **ANTES** de los imports de handlers.

El orden correcto debe ser:

```python
# Crear cliente de Pyrogram
app = Client(
    "video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Estado de usuarios (DEBE ESTAR AQUÍ)
user_states = {}

# Importar handlers (DESPUÉS)
from handlers import (
    start_handler,
    help_handler,
    ...
)
```

Guardar: `Ctrl + X`, luego `Y`, luego `Enter`

---

### Opción 3: Verificar que todos los handlers estén actualizados

```bash
cd ~/ZeroTwo

# Verificar handlers
python verify_handlers.py
```

Esto te dirá si hay algún handler con problemas.

---

## 📋 Checklist de Verificación

Revisa que estos archivos existan y estén actualizados:

```bash
cd ~/ZeroTwo
ls -la handlers/
```

Debes ver:
- ✅ `__init__.py`
- ✅ `start_handler.py`
- ✅ `help_handler.py`
- ✅ `compress_handler.py`
- ✅ `thumbnail_handler.py`
- ✅ `subtitles_handler.py`
- ✅ `extract_audio_handler.py`
- ✅ `download_handler.py`
- ✅ `anime_handler.py`
- ✅ `video_handler.py`
- ✅ `photo_handler.py`
- ✅ `document_handler.py`
- ✅ `url_handler.py`
- ✅ `button_callback_handler.py`

---

## 🔍 Verificar un Handler Específico

Para ver si un handler está correcto:

```bash
cd ~/ZeroTwo
head -15 handlers/compress_handler.py
```

Debe mostrar algo como:
```python
"""
compress_handler.py - Manejador del comando /compress
"""

from pyrogram import filters, enums
from pyrogram.types import Message


def register(app, user_states):
    """Registra el handler del comando /compress"""
    
    @app.on_message(filters.command("compress"))
    async def compress_command(client, message: Message):
```

**Nota:** La función `register()` debe tener `(app, user_states)` como parámetros.

---

## 🚀 Después de Corregir

```bash
cd ~/ZeroTwo
python main.py
```

Deberías ver:
```
╔══════════════════════════════════════════╗
║  🤖 BOT DE TELEGRAM - PROCESAMIENTO     ║
╚══════════════════════════════════════════╝
✅ FFmpeg: Instalado
✅ Megatools: Instalado
🚀 Bot iniciado correctamente
```

---

## 💡 Si Aún Tienes Problemas

Extrae los archivos limpios del tar.gz:

```bash
cd ~
rm -rf ZeroTwo
tar -xzf rikka-bot-modules.tar.gz
mv rikka-bot-modules ZeroTwo
cd ZeroTwo
echo "TU_BOT_TOKEN" > ~/.telegram_bot_token
python main.py
```

¡Esto debería funcionar al 100%!
