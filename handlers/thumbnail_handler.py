"""
thumbnail_handler.py - Manejador del comando /thumbnail
"""

from pyrogram import filters, enums
from pyrogram.types import Message


def register(app, user_states):
    """Registra el handler del comando /thumbnail"""
    
    @app.on_message(filters.command("thumbnail"))
    async def thumbnail_command(client, message: Message):
        """Comando /thumbnail - Activar modo añadir portada"""
        user_id = message.from_user.id
        user_states[user_id] = {'action': 'thumbnail', 'step': 'waiting_video'}
        
        await message.reply_text(
            "🖼️ <b>Modo Añadir Portada Activado</b>\n\n"
            "Envíame el video al que quieres añadir una portada.",
            parse_mode=enums.ParseMode.HTML
        )
