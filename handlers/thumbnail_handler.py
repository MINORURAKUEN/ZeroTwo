"""
thumbnail_handler.py - Añadir portada a videos (ULTRA RÁPIDO)
Flujo optimizado:
  1. /thumbnail
  2. Usuario envía FOTO (portada)
  3. Usuario envía VIDEO
  4. Bot procesa en 5-10 segundos (sin recodificar)
  5. Bot envía video con nueva portada

Método: ffmpeg -c copy (copia streams, solo añade portada)
"""

import logging
import subprocess
from pathlib import Path
from pyrogram import filters, enums
from pyrogram.types import Message

logger = logging.getLogger(__name__)


def register(app, user_states, work_dir):
    """Registra el handler del comando /thumbnail"""
    
    @app.on_message(filters.command(["thumbnail", "cover", "setthumb", "portada"]))
    async def thumbnail_command(client, message: Message):
        """Comando /thumbnail - Activar modo portada (foto primero)"""
        user_id = message.from_user.id
        user_states[user_id] = {
            'action': 'thumbnail',
            'step': 'waiting_image'
        }
        
        await message.reply_text(
            "🖼️ <b>Añadir Portada a Video</b>\n\n"
            "📸 <b>Paso 1:</b> Envíame la <b>FOTO</b> que quieres usar como portada.\n\n"
            "⚡ El proceso es ultra rápido (5-10 segundos)\n"
            "💡 No se recodifica el video, solo se añade la portada",
            parse_mode=enums.ParseMode.HTML
        )
    
    # Handler para recibir la IMAGEN (portada)
    @app.on_message(filters.photo)
    async def handle_thumbnail_image(client, message: Message):
        """Maneja la imagen de portada"""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        if user_id not in user_states:
            return
        
        state = user_states[user_id]
        
        if state.get('action') != 'thumbnail':
            return
        
        if state.get('step') != 'waiting_image':
            return
        
        logger.info(f"🖼️ Imagen de portada recibida de @{username}")
        
        status_msg = await message.reply_text("⬇️ Descargando imagen...")
        
        try:
            # Descargar imagen
            image_path = await message.download(
                file_name=str(work_dir / f"{user_id}_thumb.jpg")
            )
            
            logger.info(f"✅ Imagen descargada: {image_path}")
            image_size = Path(image_path).stat().st_size / 1024
            logger.info(f"📦 Tamaño de imagen: {image_size:.2f} KB")
            
            # Optimizar imagen para portada (mantener calidad alta)
            optimized_image = work_dir / f"{user_id}_thumb_optimized.jpg"
            
            logger.info("🎨 Optimizando imagen para portada...")
            optimize_cmd = [
                'ffmpeg',
                '-i', str(image_path),
                '-vf', 'scale=1920:-1',  # Max 1920px ancho
                '-q:v', '2',  # Calidad 95% (2 es muy alta)
                '-y',
                str(optimized_image)
            ]
            
            subprocess.run(
                optimize_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=True
            )
            
            if optimized_image.exists():
                logger.info(f"✅ Imagen optimizada: {optimized_image.stat().st_size / 1024:.2f} KB")
                # Guardar ruta de imagen optimizada
                user_states[user_id]['image_path'] = str(optimized_image)
            else:
                # Si falla optimización, usar original
                logger.warning("⚠️ Optimización falló, usando imagen original")
                user_states[user_id]['image_path'] = str(image_path)
            
            # Actualizar estado
            user_states[user_id]['step'] = 'waiting_video'
            
            await status_msg.edit_text(
                "✅ <b>Portada guardada</b>\n\n"
                "📹 <b>Paso 2:</b> Ahora envíame el <b>VIDEO</b> al que quieres añadir esta portada.\n\n"
                "⚡ Procesamiento rápido garantizado",
                parse_mode=enums.ParseMode.HTML
            )
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Error optimizando imagen: {e}")
            await status_msg.edit_text("❌ Error procesando la imagen. Intenta con otra.")
            del user_states[user_id]
            
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ Error: {str(e)}")
            del user_states[user_id]
    
    # Handler para recibir el VIDEO
    @app.on_message(filters.video | filters.document)
    async def handle_thumbnail_video(client, message: Message):
        """Maneja el video para añadir portada"""
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        
        if user_id not in user_states:
            return
        
        state = user_states[user_id]
        
        if state.get('action') != 'thumbnail':
            return
        
        if state.get('step') != 'waiting_video':
            return
        
        # Obtener video
        video = message.video or message.document
        
        if not video:
            return
        
        # Si es documento, verificar que sea video
        if message.document:
            if not message.document.mime_type or not message.document.mime_type.startswith('video'):
                return
        
        logger.info(f"🎬 Video recibido de @{username} para añadir portada")
        
        status_msg = await message.reply_text("⬇️ Descargando video...")
        
        # Función de progreso
        last_percent = [0]
        async def download_progress(current, total):
            percent = int((current / total) * 100)
            if percent - last_percent[0] >= 10:
                mb_current = current / (1024**2)
                mb_total = total / (1024**2)
                logger.info(f"⬇️ Descarga: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                last_percent[0] = percent
        
        try:
            # Descargar video
            video_path = await message.download(
                file_name=str(work_dir / f"{user_id}_video.mp4"),
                progress=download_progress
            )
            
            logger.info(f"✅ Video descargado: {video_path}")
            video_size = Path(video_path).stat().st_size / (1024 * 1024)
            logger.info(f"📦 Tamaño del video: {video_size:.2f} MB")
            
            # Obtener ruta de imagen
            image_path = state.get('image_path')
            
            if not image_path or not Path(image_path).exists():
                raise Exception("Imagen de portada no encontrada")
            
            await status_msg.edit_text(
                "🖼️ <b>Añadiendo portada al video...</b>\n\n"
                "⚡ Proceso ultra rápido (sin recodificar)\n"
                "⏱️ Esto tomará 5-10 segundos"
            )
            
            # Añadir portada (método ULTRA RÁPIDO con -c copy)
            output_path = work_dir / f"{user_id}_with_thumb.mp4"
            
            logger.info(f"🎬 Video: {video_path}")
            logger.info(f"🖼️ Portada: {image_path}")
            logger.info(f"📤 Salida: {output_path}")
            
            # Comando FFmpeg optimizado (SIN RECODIFICAR)
            cmd = [
                'ffmpeg',
                '-i', str(video_path),      # Video entrada
                '-i', str(image_path),       # Imagen portada
                '-map', '0',                 # Mapear todo del video
                '-map', '1',                 # Mapear la imagen
                '-c', 'copy',                # COPIAR sin recodificar
                '-disposition:v:0', 'default',      # Video principal
                '-disposition:v:1', 'attached_pic',  # Thumbnail
                '-metadata:s:v:1', 'comment=Cover (front)',
                '-y',
                str(output_path)
            ]
            
            logger.info("⚡ Ejecutando FFmpeg (ultra rápido - sin recodificar)")
            
            # Ejecutar comando — Fix: usar stdout/stderr por separado, NO capture_output
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60
            )
            
            if result.returncode != 0:
                stderr = result.stderr.decode('utf-8', errors='ignore')[:500]
                logger.error(f"❌ FFmpeg error: {stderr}")
                raise Exception("Error añadiendo portada")
            
            output_size = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Video con portada generado ({output_size:.2f} MB)")
            
            # Enviar video
            await status_msg.edit_text("📤 Enviando video con portada...")
            
            # Función de progreso para upload
            last_upload_percent = [0]
            async def upload_progress(current, total):
                percent = int((current / total) * 100)
                if percent - last_upload_percent[0] >= 10:
                    mb_current = current / (1024**2)
                    mb_total = total / (1024**2)
                    logger.info(f"📤 Subida: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                    last_upload_percent[0] = percent
            
            # Enviar como documento (archivo descargable)
            await message.reply_document(
                document=str(output_path),
                caption="✅ <b>Portada añadida exitosamente</b>\n\n⚡ Procesado en modo ultra rápido",
                parse_mode=enums.ParseMode.HTML,
                progress=upload_progress
            )
            
            logger.info("✅ Video enviado exitosamente")
            
            # Limpiar archivos temporales
            output_path.unlink()
            logger.info("🗑️ Archivo de salida eliminado")
            
            Path(image_path).unlink(missing_ok=True)
            Path(video_path).unlink(missing_ok=True)
            
            # Limpiar también imagen original si existe
            orig_img = work_dir / f"{user_id}_thumb.jpg"
            orig_img.unlink(missing_ok=True)
            
            logger.info("🗑️ Archivos temporales eliminados")
            
            await status_msg.delete()
            
            # Limpiar estado
            del user_states[user_id]
            
        except subprocess.TimeoutExpired:
            logger.error("⏱️ Timeout añadiendo portada")
            await status_msg.edit_text("⏱️ El proceso tardó demasiado. Intenta con un video más pequeño.")
            del user_states[user_id]
            
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
            await status_msg.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)
            del user_states[user_id]
          
