"""
thumbnail_handler.py - Manejador del comando /thumbnail
Flujo: /thumbnail → foto primero → video después
"""

from pyrogram import filters, enums
from pyrogram.types import Message


def register(app, user_states):
    """Registra el handler del comando /thumbnail"""

    @app.on_message(filters.command("thumbnail"))
    async def thumbnail_command(client, message: Message):
        """Comando /thumbnail - Pide primero la foto, luego el video"""
        user_id = message.from_user.id
        user_states[user_id] = {'action': 'thumbnail', 'step': 'waiting_image'}

        await message.reply_text(
            "🖼️ <b>Modo Añadir Portada Activado</b>\n\n"
            "Primero envíame la <b>foto</b> que quieres usar como portada.",
            parse_mode=enums.ParseMode.HTML
        )
