"""
video_handler.py - Manejador de videos mejorado
Soporte para: Detección de pistas internas, MKV, AVI, ISO y Subdrips.
"""

import logging
from pathlib import Path
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from utils import VideoProcessor

logger = logging.getLogger(__name__)

def register(app, user_states, work_dir):
    """Registra el handler de videos"""
    
    @app.on_message(filters.video | filters.document)
    async def handle_video(client, message: Message):
        user_id = message.from_user.id
        
        # Obtener el archivo (video o documento)
        video = message.video or message.document
        if not video:
            return
        
        # Validar extensiones soportadas
        valid_extensions = ('.mp4', '.mkv', '.avi', '.iso', '.mov', '.webm')
        file_name = video.file_name.lower() if video.file_name else ""
        
        if not file_name.endswith(valid_extensions):
            if message.document and message.document.mime_type and message.document.mime_type.startswith('video'):
                pass # Es un video sin extensión clara, procedemos
            else:
                return # No es un formato de video soportado

        logger.info(f"🎬 Video/Documento recibido: {file_name}")
        
        # Inicializar estado si no existe
        if user_id not in user_states:
            user_states[user_id] = {'step': 'waiting_video'}
        
        status_msg = await message.reply_text("⬇️ Descargando y analizando archivo...")
        
        try:
            # Descarga del archivo
            video_path = await message.download(
                file_name=str(work_dir / f"{user_id}_temp_{video.file_unique_id}{Path(file_name).suffix}")
            )
            
            # ANALIZAR PISTAS INTERNAS (Audios, Subs, Subdrips)
            tracks = VideoProcessor.probe_media(video_path)
            
            user_states[user_id].update({
                'video_path': str(video_path),
                'video_info': {
                    'size_mb': Path(video_path).stat().st_size / (1024**2),
                    'original_ext': Path(video_path).suffix
                },
                'tracks': tracks
            })

            # Construir botones dinámicos
            buttons = []
            
            # Si se detectaron pistas internas (MKV/ISO/AVI)
            if tracks and (tracks['audio'] or tracks['subtitle']):
                buttons.append([InlineKeyboardButton("🔊 Elegir Audio", callback_data="list_audio")])
                buttons.append([InlineKeyboardButton("📝 Elegir Subtítulo (Subdrips)", callback_data="list_sub")])
                buttons.append([InlineKeyboardButton("🔥 Quemar Pistas Seleccionadas", callback_data="start_burn_process")])
            
            # Opciones de compresión (siempre disponibles)
            buttons.append([InlineKeyboardButton("📉 Solo Comprimir Video", callback_data="format_mp4")])
            buttons.append([InlineKeyboardButton("🎵 Extraer Audio (MP3)", callback_data="action_extract_audio")])

            await status_msg.edit_text(
                f"✅ **Archivo analizado:** `{file_name}`\n"
                f"📦 **Tamaño:** {user_states[user_id]['video_info']['size_mb']:.2f} MB\n\n"
                f"Se detectaron {len(tracks['audio'])} audios y {len(tracks['subtitle'])} subtítulos internos.\n\n"
                "¿Qué deseas hacer?",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            await status_msg.edit_text(f"❌ Error al procesar: {str(e)}")

    # Handler extra para el caso de extracción rápida desde botones
    @app.on_callback_query(filters.regex("action_extract_audio"))
    async def cb_extract_audio(client, callback_query):
        user_id = callback_query.from_user.id
        state = user_states.get(user_id)
        if not state: return

        await callback_query.message.edit_text("🎵 Extrayendo audio...")
        output_audio = work_dir / f"{user_id}_audio.mp3"
        
        if VideoProcessor.extract_audio(state['video_path'], str(output_audio)):
            await callback_query.message.reply_audio(str(output_audio))
            output_audio.unlink()
        
        if Path(state['video_path']).exists(): Path(state['video_path']).unlink()
        del user_states[user_id]
    
