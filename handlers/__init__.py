"""
Handlers - Manejadores de comandos del bot
"""

# Importamos cada módulo de forma explícita para evitar errores de contexto
from handlers import start_handler
from handlers import help_handler
from handlers import compress_handler
from handlers import thumbnail_handler
from handlers import subtitles_handler
from handlers import extract_audio_handler
from handlers import download_handler
from handlers import anime_handler
from handlers import youtube_handler
from handlers import facebook_handler
from handlers import twitter_handler
from handlers import tiktok_handler
from handlers import video_handler
from handlers import photo_handler
from handlers import document_handler
from handlers import url_handler
from handlers import button_callback_handler
from handlers import drive_handler

# Exponemos los módulos para que main.py pueda verlos
__all__ = [
    'start_handler',
    'help_handler',
    'compress_handler',
    'thumbnail_handler',
    'subtitles_handler',
    'extract_audio_handler',
    'download_handler',
    'anime_handler',
    'youtube_handler',
    'facebook_handler',
    'twitter_handler',
    'tiktok_handler',
    'video_handler',
    'photo_handler',
    'document_handler',
    'url_handler',
    'button_callback_handler',
    'drive_handler'
]
