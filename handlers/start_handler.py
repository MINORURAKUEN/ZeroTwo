"""
start_handler.py - Manejador del comando /start
"""

from pyrogram import filters, enums
from pyrogram.types import Message


def register(app):
    """Registra el handler del comando /start"""
    
    @app.on_message(filters.command("start"))
    async def start_command(client, message: Message):
        """Comando /start - Mensaje de bienvenida"""
        
        welcome_message = """🎬 <b>Bot de Procesamiento de Videos y Descargas</b>

¡Bienvenido! Puedo ayudarte con:

📹 <b>Comprimir videos</b> - Reduce el tamaño manteniendo calidad
🖼️ <b>Añadir portadas</b> - Agrega thumbnails personalizados
📝 <b>Quemar subtítulos</b> - Integra subtítulos permanentemente
🎵 <b>Extraer audio</b> - Obtén solo el audio del video

📥 <b>Descargar de redes sociales:</b>
🎵 YouTube (videos y audio)
📘 Facebook (videos)
🐦 Twitter/X (videos e imágenes)
🔷 MEGA (mega.nz)
🔶 MediaFire (mediafire.com)

🈺 <b>Buscar anime:</b>
Obtén información completa de cualquier anime

<b>Comandos de video:</b>
/compress - Comprimir un video
/thumbnail - Añadir portada a un video
/subtitles - Quemar subtítulos en un video
/extract_audio - Extraer audio de un video

<b>Comandos de redes sociales:</b>
/play <nombre> - YouTube audio
/play2 <nombre> - YouTube video
/fb <url> - Facebook video
/x <url> - Twitter/X video/foto

<b>Comandos de descarga:</b>
/download - Descargar de MEGA o MediaFire

<b>Comandos de búsqueda:</b>
/anime - Buscar información de anime
/help - Mostrar ayuda detallada

📥 Envíame un enlace o un video para comenzar 🎥

✨ <b>Nuevo:</b> Ahora soporto archivos de cualquier tamaño!"""
        
        await message.reply_text(welcome_message, parse_mode=enums.ParseMode.HTML)
