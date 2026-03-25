"""
photo_handler.py - Manejador de imágenes (para thumbnails)
Flujo nuevo: foto primero → guarda ruta → pide el video
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
        """Maneja imágenes recibidas: guarda la foto y pide el video."""
        user_id  = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        logger.info(f"🖼️ Imagen recibida de @{username}")

        if user_id not in user_states:
            await message.reply_text("Usa /thumbnail primero para añadir una portada.")
            logger.warning(f"⚠️ Usuario {user_id} envió imagen sin estado activo")
            return

        state = user_states[user_id]

        if state.get('action') != 'thumbnail' or state.get('step') != 'waiting_image':
            logger.info("⏭️ Imagen ignorada (no está esperando foto)")
            return

        logger.info("🖼️ Descargando foto del usuario...")
        status_msg = await message.reply_text("⬇️ Descargando foto...")

        try:
            image_path = await message.download(
                file_name=str(work_dir / f"{user_id}_thumb.jpg")
            )

            logger.info(f"✅ Foto descargada: {image_path}")
            logger.info(f"📦 Tamaño: {Path(image_path).stat().st_size / 1024:.2f} KB")

            # Optimizar imagen para portada
            optimized_image = work_dir / f"{user_id}_thumb_optimized.jpg"
            optimize_cmd = [
                'ffmpeg', '-y',
                '-i', str(image_path),
                '-vf', 'scale=1920:-1',
                '-q:v', '2',
                str(optimized_image),
            ]
            try:
                subprocess.run(optimize_cmd, capture_output=True, timeout=10)
                if optimized_image.exists():
                    logger.info(f"✅ Imagen optimizada: {optimized_image.stat().st_size / 1024:.2f} KB")
                    final_image_path = str(optimized_image)
                else:
                    logger.warning("⚠️ Usando imagen original sin optimizar")
                    final_image_path = str(image_path)
            except Exception:
                logger.warning("⚠️ Error optimizando, usando imagen original")
                final_image_path = str(image_path)

            # Guardar ruta de la imagen y avanzar al siguiente paso
            state['image_path'] = final_image_path
            state['step'] = 'waiting_video'

            await status_msg.edit_text(
                "✅ <b>Foto guardada</b>\n\n"
                "Ahora envíame el <b>video</b> al que quieres añadir esta portada.",
                parse_mode=None
            )
            await status_msg.edit_text(
                "✅ Foto guardada ✔️\n\n"
                "Ahora envíame el video al que quieres añadir esta portada."
            )

        except Exception as e:
            logger.error(f"❌ Error procesando foto: {e}", exc_info=True)
            await message.reply_text(f"❌ Error: {str(e)}")
