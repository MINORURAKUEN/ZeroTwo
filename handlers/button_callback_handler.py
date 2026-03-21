"""
button_callback_handler.py - Manejador de callbacks de botones inline
"""

import logging
from pathlib import Path
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from utils import VideoProcessor

logger = logging.getLogger(__name__)


def register(app, user_states, work_dir):
    """Registra el handler de callbacks de botones"""
    
    @app.on_callback_query()
    async def button_callback(client, callback_query: CallbackQuery):
        """Maneja los callbacks de botones inline"""
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        logger.info(f"🔘 Botón presionado: {data} por usuario {user_id}")
        
        if user_id not in user_states:
            await callback_query.answer("⚠️ Sesión expirada. Envía el video de nuevo.", show_alert=True)
            return
        
        state = user_states[user_id]
        
        # Manejar selección de formato
        if data.startswith('format_'):
            format_map = {
                'format_mp4': '.mp4',
                'format_mkv': '.mkv',
                'format_avi': '.avi',
                'format_webm': '.webm',
                'format_mov': '.mov',
                'format_original': state.get('video_info', {}).get('original_ext', '.mp4')
            }
            
            output_format = format_map.get(data)
            state['output_format'] = output_format
            
            logger.info(f"📹 Formato seleccionado: {output_format}")
            
            # Ahora mostrar opciones de calidad
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📱 360p", callback_data='quality_360p'),
                    InlineKeyboardButton("📺 480p", callback_data='quality_480p')
                ],
                [
                    InlineKeyboardButton("🖥️ 720p HD", callback_data='quality_720p'),
                    InlineKeyboardButton("🎬 1080p Full HD", callback_data='quality_1080p')
                ],
                [
                    InlineKeyboardButton("⚡ Original", callback_data='quality_original')
                ]
            ])
            
            await callback_query.message.edit_text(
                f"✅ Formato seleccionado: {output_format.upper()}\n\n"
                f"Ahora selecciona la resolución:",
                reply_markup=keyboard
            )
            
            await callback_query.answer()
            return
        
        # Manejar selección de calidad
        if data.startswith('quality_'):
            resolution_map = {
                'quality_360p': {'scale': '640:360', 'bitrate': '450k', 'crf': '26', 'preset': 'medium', 'label': '360p', 'max_size_mb': None},
                'quality_480p': {'scale': '854:480', 'bitrate': '1000k', 'crf': '23', 'preset': 'medium', 'label': '480p', 'max_size_mb': None},
                'quality_720p': {'scale': '1280:720', 'bitrate': '2500k', 'crf': '23', 'preset': 'medium', 'label': '720p HD', 'max_size_mb': None},
                'quality_1080p': {'scale': '1920:1080', 'bitrate': '5000k', 'crf': '20', 'preset': 'medium', 'label': '1080p Full HD', 'max_size_mb': None},
                'quality_original': {'scale': None, 'bitrate': '3000k', 'crf': '23', 'preset': 'medium', 'label': 'Original', 'max_size_mb': None}
            }
            
            resolution_config = resolution_map.get(data)
            output_format = state.get('output_format', '.mp4')
            
            if not resolution_config:
                return
            
            scale = resolution_config['scale']
            bitrate = resolution_config['bitrate']
            crf = resolution_config['crf']
            preset = resolution_config['preset']
            label = resolution_config['label']
            max_size_mb = resolution_config['max_size_mb']
            
            logger.info(f"🎬 Iniciando compresión - Resolución: {label}, Formato: {output_format}")
            
            await callback_query.message.edit_text(
                f"⚙️ Comprimiendo video...\n"
                f"📹 Formato: {output_format.upper()}\n"
                f"📺 Resolución: {label}\n\n"
                f"Esto puede tardar varios minutos."
            )
            
            try:
                video_path = state['video_path']
                original_size = Path(video_path).stat().st_size / (1024 * 1024)
                output_path = work_dir / f"{user_id}_compressed_{label}{output_format}"
                
                logger.info(f"🎬 Video original: {video_path}")
                logger.info(f"📤 Video comprimido: {output_path}")
                
                # Comprimir video
                success = VideoProcessor.compress_video_resolution(
                    video_path, 
                    str(output_path),
                    scale=scale,
                    bitrate=bitrate,
                    crf=crf,
                    preset=preset,
                    max_size_mb=max_size_mb
                )
                
                if success:
                    compressed_size = output_path.stat().st_size / (1024 * 1024)
                    reduction = ((original_size - compressed_size) / original_size) * 100
                    
                    logger.info(f"✅ Compresión completada")
                    logger.info(f"📊 Original: {original_size:.2f} MB → Comprimido: {compressed_size:.2f} MB")
                    logger.info(f"📉 Reducción: {reduction:.1f}%")
                    
                    caption = (
                        f"✅ Video comprimido exitosamente\n\n"
                        f"📹 Formato: {output_format.upper()}\n"
                        f"📺 Resolución: {label}\n"
                        f"📊 Tamaño original: {original_size:.2f} MB\n"
                        f"📊 Tamaño comprimido: {compressed_size:.2f} MB\n"
                        f"📉 Reducción: {reduction:.1f}%"
                    )
                    
                    logger.info(f"📤 Enviando video comprimido como documento...")
                    
                    # Función de progreso para subida (más limpia)
                    last_upload_percent = [0]
                    async def upload_progress(current, total):
                        percent = int((current / total) * 100)
                        # Mostrar solo cada 10%
                        if percent - last_upload_percent[0] >= 10:
                            mb_current = current / (1024**2)
                            mb_total = total / (1024**2)
                            logger.info(f"📤 Subida: {percent}% ({mb_current:.1f}/{mb_total:.1f} MB)")
                            last_upload_percent[0] = percent
                    
                    # Enviar como documento
                    await callback_query.message.reply_document(
                        document=str(output_path),
                        caption=caption,
                        progress=upload_progress
                    )
                    
                    logger.info(f"✅ Video enviado exitosamente")
                    
                    output_path.unlink()
                    logger.info(f"🗑️ Archivo de salida eliminado")
                else:
                    logger.error("❌ Error en la compresión del video")
                    await callback_query.message.reply_text("❌ Error comprimiendo el video")
                
                Path(video_path).unlink()
                logger.info("🗑️ Video temporal eliminado")
                del user_states[user_id]
                
            except Exception as e:
                logger.error(f"❌ Error comprimiendo video: {e}", exc_info=True)
                await callback_query.message.reply_text(f"❌ Error: {str(e)}")
                
            await callback_query.answer()
