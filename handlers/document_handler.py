"""
document_handler.py - Manejador de documentos (para subtítulos)
"""

import logging
from pathlib import Path
from pyrogram import filters
from pyrogram.types import Message
from utils import VideoProcessor

logger = logging.getLogger(__name__)


def register(app, user_states, work_dir):
    """Registra el handler de documentos (subtítulos)"""
    
    @app.on_message(filters.document)
    async def handle_document(client, message: Message):
        """Maneja documentos recibidos (subtítulos)"""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        document = message.document
        
        if not document or not document.file_name:
            return
        
        # Verificar si es un archivo de subtítulos
        if not document.file_name.endswith(('.srt', '.ass', '.vtt')):
            # No es un subtítulo, podría ser un video
            # Manejado por video_handler
            return
        
        logger.info(f"📝 Archivo de subtítulos recibido de @{username}")
        
        if user_id not in user_states:
            await message.reply_text("Usa /subtitles primero para quemar subtítulos.")
            logger.warning(f"⚠️ Usuario {user_id} envió subtítulos sin estado activo")
            return
        
        state = user_states[user_id]
        
        if state.get('action') != 'subtitles' or state.get('step') != 'waiting_subtitle':
            logger.info(f"⏭️ Subtítulos ignorados (no está en modo subtitles)")
            return
        
        logger.info(f"📝 Procesando subtítulos")
        
        status_msg = await message.reply_text("⬇️ Descargando subtítulos...")
        
        try:
            subtitle_path = await message.download(
                file_name=str(work_dir / f"{user_id}_subs{Path(document.file_name).suffix}")
            )
            
            logger.info(f"✅ Subtítulos descargados: {subtitle_path}")
            
            await status_msg.edit_text("📝 Quemando subtítulos en el video...")
            
            video_path = state['video_path']
            output_path = work_dir / f"{user_id}_with_subs.mp4"
            
            logger.info(f"🎬 Video original: {video_path}")
            logger.info(f"📤 Video con subtítulos: {output_path}")
            
            if VideoProcessor.burn_subtitles(video_path, subtitle_path, str(output_path)):
                output_size = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Video con subtítulos generado ({output_size:.2f} MB)")
                logger.info(f"📤 Enviando video al usuario como documento...")
                
                # Función de progreso para subida
                last_upload_percent = [0]
                async def upload_progress(current, total):
                    percent = int((current / total) * 100)
                    if percent - last_upload_percent[0] >= 10:
                        mb_current = current / (1024**2)
                        mb_total = total / (1024**2)
                        logger.info(f"📤 Subida: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                        last_upload_percent[0] = percent
                
                # Enviar como documento
                await message.reply_document(
                    document=str(output_path),
                    caption="✅ Subtítulos quemados exitosamente",
                    progress=upload_progress
                )
                
                logger.info(f"✅ Video enviado exitosamente")
                
                output_path.unlink()
                logger.info("🗑️ Archivo de salida eliminado")
            else:
                logger.error("❌ Error quemando subtítulos")
                await message.reply_text("❌ Error quemando subtítulos")
            
            Path(subtitle_path).unlink()
            logger.info("🗑️ Archivo de subtítulos eliminado")
            
            Path(video_path).unlink()
            logger.info("🗑️ Video temporal eliminado")
            
            del user_states[user_id]
            
        except Exception as e:
            logger.error(f"❌ Error procesando subtítulos: {e}", exc_info=True)
            await message.reply_text(f"❌ Error: {str(e)}")
