"""
help_handler.py - Manejador del comando /help
"""

from pyrogram import filters, enums
from pyrogram.types import Message


def register(app):
    """Registra el handler del comando /help"""
    
    @app.on_message(filters.command("help"))
    async def help_command(client, message: Message):
        """Comando /help - Ayuda detallada"""
        
        help_text = """📖 <b>Ayuda Detallada</b>

<b>PROCESAMIENTO DE VIDEOS:</b>

<b>1️⃣ Comprimir Video:</b>
- Envía /compress o envía un video directamente
- Funciona con videos de cualquier tamaño ✨
- Elige el formato y resolución
- Los videos se envían como archivo descargable

<b>2️⃣ Añadir Portada:</b>
- Envía /thumbnail
- Envía el video
- Envía la imagen para la portada
- Recibe el video con portada

<b>3️⃣ Quemar Subtítulos:</b>
- Envía /subtitles
- Envía el video
- Envía el archivo de subtítulos (.srt, .ass)
- Recibe el video con subtítulos integrados

<b>4️⃣ Extraer Audio:</b>
- Envía /extract_audio
- Envía el video
- Recibe el archivo de audio en MP3

<b>DESCARGAS DE REDES SOCIALES:</b>

<b>5️⃣ YouTube:</b>
- /play <nombre> - Descargar audio
- /play2 <nombre> - Descargar video
- /playaudio <nombre> - Audio como nota de voz
- /ytmp3 <url> - Audio desde URL
- /ytmp4 <url> - Video desde URL
- Ejemplo: /play Linkin Park Numb

<b>6️⃣ Facebook:</b>
- /fb <url> - Descargar video de Facebook
- Ejemplo: /fb https://facebook.com/watch/?v=12345

<b>7️⃣ Twitter/X:</b>
- /x <url> - Descargar video o fotos de Twitter/X
- Ejemplo: /x https://x.com/user/status/123456789

<b>8️⃣ Mejorar Imagen con IA:</b>
- /enhance, /hd o /remini
- Responde a una foto o envíala adjunta
- Aplica upscale 4x con IA
- Ejemplo: /enhance (respondiendo a una imagen)

<b>9️⃣ MEGA/MediaFire/Drive:</b>
- Envía /download o pega directamente el enlace
- Servicios soportados:
  🔷 MEGA (mega.nz, mega.co.nz)
  🔶 MediaFire (mediafire.com)
  ☁️ Google Drive (/gdrive <url>)
  📤 Subir a Drive (/gdrive_upload)

<b>BÚSQUEDA:</b>

<b>🔟 Buscar Anime:</b>
- Envía /anime Nombre del anime
- Obtén información completa con imagen
- Ejemplo: /anime One Piece

<b>Ejemplos de enlaces:</b>
• YouTube: youtube.com/watch?v=abc123
• Facebook: facebook.com/watch/?v=12345
• Twitter: x.com/user/status/123456789
• MEGA: mega.nz/file/abc123#xyz789
• MediaFire: mediafire.com/file/abc123/archivo.zip

<b>Formatos soportados:</b>
- Descargas: Videos se envían como video reproducible
- Compresión: Videos se envían como archivo descargable
- Subtítulos: SRT, ASS, VTT
- Imágenes: JPG, PNG
- Audio: MP3, M4A, WAV, OGG, FLAC

<b>Límites:</b>
- Videos: Sin límite de tamaño para descargar ✨
- Archivos procesados: Máx. 2GB para enviar (límite de Telegram)
- Tiempo de procesamiento: Depende del tamaño

<b>💡 Tip:</b> Ahora puedes descargar de YouTube, Facebook y Twitter!

¿Necesitas ayuda? Contáctame con /start"""
        
        await message.reply_text(help_text, parse_mode=enums.ParseMode.HTML)
