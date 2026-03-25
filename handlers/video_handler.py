"""
video_handler.py - Manejador de videos recibidos
"""

import logging
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils import VideoProcessor

logger = logging.getLogger(__name__)


def register(app, user_states, work_dir):
    """Registra el handler de videos"""
    
    @app.on_message(filters.video | filters.document)
    async def handle_video(client, message: Message):
        """Maneja videos y documentos recibidos"""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        # Obtener el archivo (video o documento)
        video = message.video or message.document
        
        if not video:
            return
        
        # Si es documento, verificar que sea video
        if message.document:
            if not message.document.mime_type or not message.document.mime_type.startswith('video'):
                # Si es archivo de subtítulos
                if message.document.file_name and message.document.file_name.endswith(('.srt', '.ass', '.vtt')):
                    # Manejado por document_handler
                    return
                return
        
        logger.info(f"🎬 Video recibido de @{username}")
        
        # Verificar si hay un estado activo
        if user_id not in user_states:
            # No hay estado, activar modo compresión por defecto
            user_states[user_id] = {'action': 'compress', 'step': 'waiting_video'}
            logger.info(f"🔧 Activando modo compresión automático para {user_id}")
        
        state = user_states[user_id]
        action = state.get('action')
        step = state.get('step')
        
        if step != 'waiting_video':
            logger.info(f"⏭️ Video ignorado (no está esperando video)")
            return
        
        file_size = video.file_size / (1024 * 1024)
        logger.info(f"📦 Tamaño del video: {file_size:.2f} MB")
        
        status_msg = await message.reply_text("⬇️ Descargando video...")
        logger.info(f"⬇️ Iniciando descarga del video desde Telegram...")
        
        # Función de progreso (más limpia)
        last_download_percent = [0]
        async def download_progress(current, total):
            percent = int((current / total) * 100)
            # Mostrar solo cada 10%
            if percent - last_download_percent[0] >= 10:
                mb_current = current / (1024**2)
                mb_total = total / (1024**2)
                logger.info(f"⬇️ Descarga: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                last_download_percent[0] = percent
        
        try:
            # Pyrogram descarga archivos grandes sin problemas
            video_path = await message.download(
                file_name=str(work_dir / f"{user_id}_video_{video.file_unique_id}.mp4"),
                progress=download_progress
            )
            
            logger.info(f"✅ Video descargado en: {video_path}")
            logger.info(f"📁 Tamaño en disco: {Path(video_path).stat().st_size / (1024**2):.2f} MB")
            
            user_states[user_id]['video_path'] = str(video_path)
            
            if action == 'compress':
                logger.info("🎛️ Mostrando opciones de compresión al usuario")
                # Guardar información del video para el siguiente paso
                user_states[user_id]['video_info'] = {
                    'size_mb': Path(video_path).stat().st_size / (1024**2),
                    'original_ext': Path(video_path).suffix
                }
                
                # Primero preguntar por el formato
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("📄 MP4 (Archivo)", callback_data='format_mp4'),
                        InlineKeyboardButton("📄 MKV (Archivo)", callback_data='format_mkv')
                    ],
                    [
                        InlineKeyboardButton("📄 AVI (Archivo)", callback_data='format_avi'),
                        InlineKeyboardButton("📄 WEBM (Archivo)", callback_data='format_webm')
                    ],
                    [
                        InlineKeyboardButton("📄 MOV (Archivo)", callback_data='format_mov'),
                        InlineKeyboardButton("⚡ Mantener original", callback_data='format_original')
                    ]
                ])
                
                await status_msg.edit_text(
                    "✅ Video descargado\n\n"
                    "📦 Tamaño: {:.2f} MB\n\n"
                    "Selecciona el formato de salida:".format(
                        user_states[user_id]['video_info']['size_mb']
                    ),
                    reply_markup=keyboard
                )
                
            elif action == 'thumbnail':
                # La foto ya fue recibida antes — procesar directamente
                image_path = state.get('image_path')
                if not image_path:
                    logger.error("❌ No se encontró la ruta de la imagen en el estado")
                    await status_msg.edit_text("❌ Error interno: no se encontró la foto guardada. Usa /thumbnail de nuevo.")
                    Path(video_path).unlink(missing_ok=True)
                    del user_states[user_id]
                    return

                logger.info(f"🖼️ Aplicando portada al video con imagen: {image_path}")
                await status_msg.edit_text("🖼️ Añadiendo portada al video...")

                output_path = work_dir / f"{user_id}_with_thumb.mp4"

                if VideoProcessor.add_thumbnail_fast(video_path, image_path, str(output_path)):
                    output_size = output_path.stat().st_size / (1024 * 1024)
                    logger.info(f"✅ Portada añadida ({output_size:.2f} MB)")
                    logger.info("📤 Enviando video al usuario como documento...")

                    last_upload_percent = [0]
                    async def upload_progress(current, total):
                        percent = int((current / total) * 100)
                        if percent - last_upload_percent[0] >= 10:
                            mb_current = current / (1024**2)
                            mb_total   = total   / (1024**2)
                            logger.info(f"📤 Subida: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                            last_upload_percent[0] = percent

                    await message.reply_document(
                        document=str(output_path),
                        caption="✅ Portada añadida exitosamente",
                        progress=upload_progress
                    )

                    logger.info("✅ Video enviado exitosamente")
                    output_path.unlink(missing_ok=True)
                else:
                    logger.error("❌ Error añadiendo portada")
                    await message.reply_text("❌ Error añadiendo la portada al video")

                # Limpiar imagen y video temporales
                Path(image_path).unlink(missing_ok=True)
                orig_thumb = work_dir / f"{user_id}_thumb.jpg"
                orig_thumb.unlink(missing_ok=True)
                Path(video_path).unlink(missing_ok=True)
                logger.info("🗑️ Archivos temporales eliminados")
                del user_states[user_id]
                
            elif action == 'subtitles':
                logger.info("📝 Esperando archivo de subtítulos")
                user_states[user_id]['step'] = 'waiting_subtitle'
                await status_msg.edit_text(
                    "✅ Video descargado\n\n"
                    "Ahora envíame el archivo de subtítulos (.srt, .ass, .vtt)."
                )
                
            elif action == 'extract_audio':
                logger.info("🎵 Extrayendo audio del video")
                await status_msg.edit_text("🎵 Extrayendo audio del video...")
                
                output_path = work_dir / f"{user_id}_audio.mp3"
                
                if VideoProcessor.extract_audio(video_path, str(output_path)):
                    logger.info(f"✅ Audio extraído exitosamente")
                    logger.info(f"📤 Enviando audio al usuario...")
                    
                    await message.reply_audio(
                        audio=str(output_path),
                        caption="✅ Audio extraído exitosamente"
                    )
                    
                    logger.info(f"✅ Audio enviado exitosamente")
                    
                    output_path.unlink()
                    logger.info("🗑️ Archivo de audio temporal eliminado")
                else:
                    logger.error("❌ Error extrayendo el audio")
                    await message.reply_text("❌ Error extrayendo el audio")
                
                Path(video_path).unlink()
                logger.info("🗑️ Video temporal eliminado")
                del user_states[user_id]
                
        except Exception as e:
            logger.error(f"❌ Error procesando video: {e}", exc_info=True)
            await message.reply_text(f"❌ Error: {str(e)}")
