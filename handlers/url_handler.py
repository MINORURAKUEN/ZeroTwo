"""
url_handler.py - Manejador de URLs (descargas MEGA/MediaFire)
"""

import re
import logging
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message
from downloaders import MEGADownloader, MediaFireDownloader

logger = logging.getLogger(__name__)


def register(app, download_dir):
    """Registra el handler de URLs"""
    
    @app.on_message(filters.text & filters.regex(r'https?://'))
    async def handle_url(client, message: Message):
        """Maneja URLs para descargas"""
        url = message.text.strip()
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        logger.info(f"🔗 URL recibida de @{username}: {url[:80]}...")
        
        # Determinar el servicio
        service_name = None
        is_mega = MEGADownloader.is_mega_url(url)
        is_mediafire = MediaFireDownloader.is_mediafire_url(url)
        
        if not is_mega and not is_mediafire:
            logger.info(f"⏭️ URL no es de MEGA ni MediaFire, ignorando")
            return
        
        if is_mega:
            service_name = "MEGA"
            logger.info("✅ Servicio detectado: MEGA")
        elif is_mediafire:
            service_name = "MediaFire"
            logger.info("✅ Servicio detectado: MEDIAFIRE")
        
        # Crear directorio temporal para este usuario
        user_download_dir = download_dir / f"user_{user_id}"
        user_download_dir.mkdir(exist_ok=True)
        
        status_msg = await message.reply_text(
            f"📥 <b>Iniciando descarga desde {service_name}</b>\n\n"
            f"Esto puede tardar varios minutos...",
            parse_mode=enums.ParseMode.HTML
        )
        
        # Callback de progreso
        async def progress_callback(text):
            try:
                await status_msg.edit_text(text)
            except:
                pass
        
        try:
            # Descargar según el servicio
            if is_mega:
                success, file_path, error = await MEGADownloader.download(
                    url, user_download_dir, progress_callback
                )
            else:
                success, file_path, error = await MediaFireDownloader.download(
                    url, user_download_dir, progress_callback
                )
            
            if not success:
                await status_msg.edit_text(
                    f"❌ <b>Error descargando de {service_name}</b>\n\n"
                    f"{error}",
                    parse_mode=enums.ParseMode.HTML
                )
                return
            
            # Archivo descargado exitosamente
            logger.info(f"✅ Descarga completada: {file_path}")
            
            file_size = file_path.stat().st_size / (1024 * 1024)
            filename = file_path.name
            file_ext = file_path.suffix.lower()
            
            logger.info(f"📦 Tamaño del archivo: {file_size:.2f} MB")
            logger.info(f"📤 Preparando envío de archivo ({file_ext})...")
            
            await status_msg.edit_text(
                f"✅ <b>Descarga completada</b>\n\n"
                f"📦 Tamaño: {file_size:.2f} MB\n"
                f"📤 Enviando archivo...",
                parse_mode=enums.ParseMode.HTML
            )
            
            # Función de progreso para Pyrogram (más limpia)
            last_send_percent = [0]
            async def progress(current, total):
                percent = int((current / total) * 100)
                # Mostrar solo cada 10%
                if percent - last_send_percent[0] >= 10:
                    mb_current = current / (1024**2)
                    mb_total = total / (1024**2)
                    logger.info(f"📤 Enviando: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                    last_send_percent[0] = percent
            
            # Enviar archivo según su tipo
            try:
                if file_ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
                    logger.info("🎬 Enviando como video...")
                    await message.reply_video(
                        video=str(file_path),
                        caption=f"✅ Descargado de {service_name}",
                        supports_streaming=True,
                        progress=progress
                    )
                elif file_ext in ['.mp3', '.m4a', '.wav', '.ogg', '.flac']:
                    logger.info("🎵 Enviando como audio...")
                    await message.reply_audio(
                        audio=str(file_path),
                        caption=f"✅ Descargado de {service_name}",
                        progress=progress
                    )
                elif file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    logger.info("🖼️ Enviando como imagen...")
                    await message.reply_photo(
                        photo=str(file_path),
                        caption=f"✅ Descargado de {service_name}",
                        progress=progress
                    )
                else:
                    logger.info(f"📄 Enviando como documento: {filename}")
                    await message.reply_document(
                        document=str(file_path),
                        caption=f"✅ Descargado de {service_name}\n📦 {filename}",
                        progress=progress
                    )
                
                logger.info("✅ Archivo enviado exitosamente al usuario")
                await status_msg.delete()
                
            except Exception as e:
                logger.error(f"❌ Error enviando archivo: {e}")
                await status_msg.edit_text(
                    f"❌ Error enviando el archivo\n\n"
                    f"El archivo es muy grande o hubo un problema."
                )
            
            # Limpiar archivo temporal
            file_path.unlink()
            logger.info(f"🗑️ Archivo temporal eliminado")
            
        except Exception as e:
            logger.error(f"❌ Error en descarga: {e}", exc_info=True)
            await status_msg.edit_text(
                f"❌ <b>Error descargando</b>\n\n"
                f"Detalles: {str(e)[:100]}",
                parse_mode=enums.ParseMode.HTML
            )
