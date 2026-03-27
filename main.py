#!/usr/bin/env python3
"""
Rikka Bot - Bot de Telegram para procesamiento de videos
Autor: @MINORURAKUEN
GitHub: https://github.com/MINORURAKUEN/Rikka-Bot
"""

import os
import logging
import asyncio
import subprocess
from pathlib import Path
from pyrogram import Client, idle

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

# Configuración del bot
API_ID = 30368923
API_HASH = "c77e78f4666683cb542fe4a2f7fd9045"

# Leer token del bot
token_file = Path.home() / '.telegram_bot_token'
if not token_file.exists():
    logger.error("❌ No se encontró el archivo ~/.telegram_bot_token")
    logger.error("Crea el archivo con: echo 'TU_BOT_TOKEN' > ~/.telegram_bot_token")
    exit(1)

BOT_TOKEN = token_file.read_text().strip()

# Directorios de trabajo
WORK_DIR = Path.home() / 'telegram_bot_files'
DOWNLOAD_DIR = Path.home() / 'telegram_downloads'

WORK_DIR.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Crear cliente de Pyrogram
app = Client(
    "video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Estado de usuarios
user_states = {}

# Importar handlers
from handlers import (
    start_handler, help_handler, compress_handler,
    thumbnail_handler, subtitles_handler, extract_audio_handler,
    download_handler, anime_handler, youtube_handler,
    facebook_handler, twitter_handler, tiktok_handler,
    video_handler, photo_handler, document_handler,
    url_handler, button_callback_handler, drive_handler,
    enhance_handler, notify_handler
)

# --- REGISTRO DE HANDLERS ---
# Se corrigieron los argumentos pasando WORK_DIR donde era requerido
start_handler.register(app)
help_handler.register(app)
compress_handler.register(app, user_states, WORK_DIR) # Añadido WORK_DIR
thumbnail_handler.register(app, user_states, WORK_DIR) # CORRECCIÓN AQUÍ ✅
subtitles_handler.register(app, user_states, WORK_DIR) # Añadido WORK_DIR
extract_audio_handler.register(app, user_states, WORK_DIR) # Añadido WORK_DIR
download_handler.register(app)
anime_handler.register(app, user_states, WORK_DIR)
youtube_handler.register(app, DOWNLOAD_DIR)
facebook_handler.register(app, DOWNLOAD_DIR)
twitter_handler.register(app, DOWNLOAD_DIR)
tiktok_handler.register(app, DOWNLOAD_DIR)
video_handler.register(app, user_states, WORK_DIR)
photo_handler.register(app, user_states, WORK_DIR)
document_handler.register(app, user_states, WORK_DIR)
url_handler.register(app, DOWNLOAD_DIR)
button_callback_handler.register(app, user_states, WORK_DIR)
drive_handler.register(app, user_states, DOWNLOAD_DIR)
enhance_handler.register(app, user_states, WORK_DIR)
notify_handler.register(app)

async def check_tools():
    """Verifica si las herramientas externas están instaladas"""
    logger.info("🔍 Verificando herramientas necesarias...")
    tools = {
        'FFmpeg': 'ffmpeg',
        'FFprobe': 'ffprobe',
        'Megatools': 'megadl',
        'Wget': 'wget'
    }
    for name, cmd in tools.items():
        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()
            if proc.returncode == 0:
                logger.info(f"✅ {name}: Instalado")
            else:
                logger.warning(f"⚠️ {name}: No disponible")
        except Exception:
            logger.warning(f"⚠️ {name}: No disponible")

async def main():
    logger.info("=" * 60)
    logger.info("🤖 BOT DE TELEGRAM - RIKKA BOT INICIANDO")
    logger.info("=" * 60)
    
    await check_tools()
    
    # Iniciar cliente
    await app.start()
    
    # Lanzar loop de notificaciones en segundo plano
    asyncio.create_task(notify_handler.background_loop(app))
    logger.info("🔔 Loop de notificaciones lanzado")
    
    logger.info("🚀 Bot iniciado correctamente")
    logger.info("⏸️ Presiona Ctrl+C para detener")
    logger.info("=" * 60)
    
    # Mantener el bot corriendo
    await idle()
    
    # Detener con gracia
    await app.stop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Bot detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}", exc_info=True)
    
