"""
photo_handler.py - Manejador de imágenes (para thumbnails)
"""

import logging
import subprocess
from pathlib import Path
from pyrogram import filters
from pyrogram.types import Message
from utils import VideoProcessor

logger = logging.getLogger(__name__)


def register(app, user_states, work_dir):
    """Registra el handler de imágenes"""
    
    @app.on_message(filters.photo)
    async def handle_photo(client, message: Message):
        """Maneja imágenes recibidas (para thumbnails)"""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        logger.info(f"🖼️ Imagen recibida de @{username}")
        
        if user_id not in user_states:
            await message.reply_text("Usa /thumbnail primero para añadir una portada.")
            logger.warning(f"⚠️ Usuario {user_id} envió imagen sin estado activo")
            return
        
        state = user_states[user_id]
        
        if state.get('action') != 'thumbnail' or state.get('step') != 'waiting_image':
            logger.info(f"⏭️ Imagen ignorada (no está en modo thumbnail)")
            return
        
        logger.info(f"🖼️ Procesando imagen como thumbnail")
        
        status_msg = await message.reply_text("⬇️ Descargando imagen...")
        
        try:
            image_path = await message.download(
                file_name=str(work_dir / f"{user_id}_thumb.jpg")
            )
            
            logger.info(f"✅ Imagen descargada: {image_path}")
            image_size = Path(image_path).stat().st_size / 1024
            logger.info(f"📦 Tamaño de imagen original: {image_size:.2f} KB")
            
            # Optimizar imagen para portada (alta calidad)
            optimized_image = work_dir / f"{user_id}_thumb_optimized.jpg"
            
            logger.info("🎨 Optimizando imagen para portada...")
            optimize_cmd = [
                'ffmpeg',
                '-i', str(image_path),
                '-vf', 'scale=1920:-1',  # Mantener aspect ratio, max 1920px ancho
                '-q:v', '2',  # Calidad muy alta (2 = ~95% calidad JPEG)
                '-y',
                str(optimized_image)
            ]
            
            try:
                subprocess.run(optimize_cmd, capture_output=True, timeout=10)
                if optimized_image.exists():
                    logger.info(f"✅ Imagen optimizada: {optimized_image.stat().st_size / 1024:.2f} KB")
                    image_path = str(optimized_image)
                else:
                    logger.warning("⚠️ Usando imagen original")
            except:
                logger.warning("⚠️ Error optimizando, usando imagen original")
            
            await status_msg.edit_text("🖼️ Añadiendo portada al video...")
            
            video_path = state['video_path']
            output_path = work_dir / f"{user_id}_with_thumb.mp4"
            
            logger.info(f"🎬 Video original: {video_path}")
            logger.info(f"📤 Video con portada: {output_path}")
            
            if VideoProcessor.add_thumbnail_fast(video_path, str(image_path), str(output_path)):
                output_size = output_path.stat().st_size / (1024 * 1024)
                logger.info(f"✅ Video con portada generado ({output_size:.2f} MB)")
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
                    caption="✅ Portada añadida exitosamente",
                    progress=upload_progress
                )
                
                logger.info(f"✅ Video enviado exitosamente")
                output_path.unlink()
                logger.info(f"🗑️ Archivo de salida eliminado")
                
                # Limpiar imagen original y optimizada
                Path(image_path).unlink(missing_ok=True)
                optimized_img = work_dir / f"{user_id}_thumb_optimized.jpg"
                optimized_img.unlink(missing_ok=True)
                logger.info("🗑️ Imágenes temporales eliminadas")
            else:
                logger.error("❌ Error añadiendo la portada")
                await message.reply_text("❌ Error añadiendo la portada al video")
            
            Path(video_path).unlink()
            logger.info("🗑️ Video temporal eliminado")
            del user_states[user_id]
            
        except Exception as e:
            logger.error(f"❌ Error procesando thumbnail: {e}", exc_info=True)
            await message.reply_text(f"❌ Error: {str(e)}")
